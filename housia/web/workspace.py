"""Import, screen, reply and book imported enquiries."""

from datetime import datetime, timedelta

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for

from housia import config, core, db
from housia.services import workspace

bp = Blueprint('workspace', __name__)
STEPS = {'import': 'Import', 'screen': 'Screen', 'reply': 'Reply', 'agenda': 'Viewings'}


def property_or_404(conn, property_id):
    row = conn.execute('SELECT * FROM properties WHERE id = ?', (property_id,)).fetchone()
    if row is None:
        abort(404)
    return row


def context(conn, prop, step):
    now = core.now(conn).isoformat()
    minimum = workspace.minimum_income(conn, prop['id'])
    people = []
    for row in workspace.enquiries(conn, prop['id']):
        person = dict(row)
        person['result'], person['evidence'] = workspace.screening(row, minimum)
        person['drafts'] = workspace.drafts(row, prop['title']) if step == 'reply' else {}
        person['channel_name'], person['channel_url'] = workspace.CHANNELS[row['channel']]
        if row['channel'] == 'whatsapp' and step == 'reply':
            person['channel_url'] = 'https://wa.me/' + row['thread_ref'][1:]
        people.append(person)
    slots = conn.execute(
        'SELECT s.*, a.name FROM slots s LEFT JOIN applications a ON a.id = s.booked_application_id '
        'WHERE s.property_id = ? AND s.starts_at > ? ORDER BY s.starts_at', (prop['id'], now),
    ).fetchall()
    return dict(step=step, steps=STEPS, people=people, minimum=minimum, slots=slots,
                channels=workspace.CHANNELS, selected_channel=request.args.get('channel', ''),
                result_filter=request.args.get('result', 'all'),
                ai_enabled=bool(config.WORKSPACE_AI_NOTES and config.REPLY_MODEL and config.OPENAI_API_KEY))


def _back(property_id, step):
    return redirect(url_for('properties.detail', property_id=property_id, step=step))


@bp.get('/workspace/import-template/<channel>.csv')
def sample(channel):
    if channel not in workspace.CHANNELS:
        abort(404)
    ref = '+34600123456' if channel == 'whatsapp' else 'conversation-123'
    return Response(f'name,thread_ref\nJamie Rivera,{ref}\n', mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename="housia-enquiries.csv"'})


@bp.post('/properties/<int:property_id>/workspace/import')
def import_leads(property_id):
    channel = request.form.get('channel')
    if channel not in workspace.CHANNELS:
        abort(400)
    try:
        rows = workspace.read_csv(request.files.get('enquiries'), channel)
        with db.tx() as conn:
            property_or_404(conn, property_id)
            count = workspace.import_rows(conn, property_id, channel, rows)
        duplicates = len(rows) - count
        flash(f'Imported: {count}. Duplicates skipped: {duplicates}.')
    except core.DomainError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('properties.detail', property_id=property_id, step='import', channel=channel))
    return _back(property_id, 'import')


@bp.post('/properties/<int:property_id>/workspace/brief')
def save_brief(property_id):
    try:
        minimum = int(request.form.get('min_net_eur', ''))
        if not 0 <= minimum <= 1_000_000:
            raise ValueError
    except ValueError:
        flash('Enter a monthly minimum between €0 and €1,000,000.', 'error')
        return _back(property_id, 'screen')
    with db.tx() as conn:
        property_or_404(conn, property_id)
        conn.execute('INSERT INTO screening_briefs (property_id, min_net_eur) VALUES (?, ?) '
                     'ON CONFLICT (property_id) DO UPDATE SET min_net_eur = excluded.min_net_eur',
                     (property_id, minimum))
    flash('Screening brief updated.')
    return _back(property_id, 'screen')


def _person(conn, property_id, app_id):
    row = conn.execute(
        'SELECT e.*, a.name, a.status FROM imported_enquiries e JOIN applications a ON a.id = e.application_id '
        'WHERE e.property_id = ? AND e.application_id = ?', (property_id, app_id),
    ).fetchone()
    if row is None:
        abort(404)
    return row


@bp.post('/properties/<int:property_id>/workspace/enquiries/<int:app_id>/explain')
def explain(property_id, app_id):
    with db.tx() as conn:
        row = _person(conn, property_id, app_id)
        state, _ = workspace.screening(row, workspace.minimum_income(conn, property_id))
    note = workspace.ai_note(state)
    if note:
        flash(f'AI screening note: {note}')
    else:
        flash('The AI explanation is unavailable. You can still review the screening result.', 'error')
    return _back(property_id, 'screen')


@bp.post('/properties/<int:property_id>/workspace/enquiries/<int:app_id>/decision')
def decision(property_id, app_id):
    choice = request.form.get('decision')
    if choice not in {'invite', 'decline'}:
        abort(400)
    try:
        with db.tx() as conn:
            row = _person(conn, property_id, app_id)
            if row['decision_sent_at']:
                raise core.DomainError('A decision has already been recorded.')
            now = core.now(conn)
            if choice == 'invite':
                prop = property_or_404(conn, property_id)
                if not row['document_received'] or row['status'] != 'docs_uploaded':
                    raise core.DomainError('The applicant must submit a payslip before you can invite them.')
                if core.invited_count(conn, property_id) >= prop['invite_limit']:
                    raise core.DomainError('You have reached the viewing invitation limit. Edit the property to increase it.')
                conn.execute("UPDATE applications SET calendar_access = 1, status = 'invited', invited_by = 'landlord' WHERE id = ?", (app_id,))
            else:
                core.set_status(conn, app_id, 'closed')
            conn.execute('UPDATE imported_enquiries SET decision = ?, decision_sent_at = ?, net_pay_cents = NULL '
                         'WHERE application_id = ?', (choice, now.isoformat(), app_id))
        flash(f'Recorded your reply on {workspace.CHANNELS[row["channel"]][0]}.' +
              (' The viewing link is now active.' if choice == 'invite' else ''))
    except core.DomainError as exc:
        flash(str(exc), 'error')
    return _back(property_id, 'reply')


@bp.post('/properties/<int:property_id>/workspace/slots')
def add_slot(property_id):
    try:
        starts = datetime.strptime(request.form.get('starts_at', ''), '%Y-%m-%dT%H:%M')
        minutes = int(request.form.get('duration_min', ''))
        if not 10 <= minutes <= 180:
            raise ValueError
        with db.tx() as conn:
            property_or_404(conn, property_id)
            if starts <= core.now(conn):
                raise core.DomainError('Choose a date and time in the future.')
            if any(starts < datetime.fromisoformat(s['starts_at']) + timedelta(minutes=s['duration_min'])
                   and datetime.fromisoformat(s['starts_at']) < starts + timedelta(minutes=minutes)
                   for s in conn.execute('SELECT starts_at, duration_min FROM slots')):
                raise core.DomainError('This time overlaps another slot in your agenda.')
            conn.execute('INSERT INTO slots (property_id, starts_at, duration_min) VALUES (?, ?, ?)',
                         (property_id, starts.isoformat(), minutes))
        flash('Viewing slot added.')
    except ValueError:
        flash('Enter a valid date, time and duration (10–180 minutes).', 'error')
    except core.DomainError as exc:
        flash(str(exc), 'error')
    return _back(property_id, 'agenda')


@bp.post('/properties/<int:property_id>/workspace/slots/<int:slot_id>/remove')
def remove_slot(property_id, slot_id):
    with db.tx() as conn:
        count = conn.execute(
            'DELETE FROM slots WHERE id = ? AND property_id = ? AND booked_application_id IS NULL '
            'AND offer_application_id IS NULL AND NOT EXISTS (SELECT 1 FROM waitlist WHERE slot_id = ?)',
            (slot_id, property_id, slot_id),
        ).rowcount
    flash('Viewing slot removed.' if count else 'This slot is no longer open.', 'success' if count else 'error')
    return _back(property_id, 'agenda')


def _candidate(conn, token):
    row = conn.execute('SELECT a.* FROM applications a JOIN imported_enquiries e ON a.id = e.application_id '
                       'WHERE a.token = ?', (token,)).fetchone()
    if row is None:
        abort(404)
    return row


def _change_booking(conn, person, action, slot_id):
    if not person['calendar_access']:
        raise core.DomainError('Your viewing invitation is not active.')
    now = core.now(conn)
    slot = conn.execute('SELECT * FROM slots WHERE property_id = ? AND id = ?',
                        (person['property_id'], slot_id)).fetchone()
    if not slot or slot['starts_at'] <= now.isoformat():
        raise core.DomainError('This viewing slot is no longer available.')
    if action == 'book':
        if slot['booked_application_id'] or slot['offer_application_id']:
            raise core.DomainError('This slot has been taken. Please choose another time.')
        if person['status'] != 'invited':
            raise core.DomainError('Cancel your current viewing before booking again.')
        booked, status, verb = person['id'], 'booked', 'booked'
    else:
        if slot['booked_application_id'] != person['id']:
            raise core.DomainError('This booking does not belong to you.')
        booked, status, verb = None, 'invited', 'cancelled'
    conn.execute('UPDATE slots SET booked_application_id = ? WHERE id = ?', (booked, slot_id))
    core.set_status(conn, person['id'], status)
    when = datetime.fromisoformat(slot['starts_at']).strftime('%a %d %b at %H:%M')
    core.notify(conn, property_id=person['property_id'], application_id=None, title=f'Viewing {verb}',
                body=f'{person["name"]} {verb} their viewing for {when}.', now=now)
    flash(f'Your viewing was {verb}.')


@bp.route('/viewing/<token>', methods=['GET', 'POST'])
def candidate(token):
    if request.method == 'POST':
        try:
            action = request.form.get('action')
            if action == 'upload':
                with db.tx() as conn:
                    if _candidate(conn, token)['status'] not in {'docs_requested', 'docs_uploaded'}:
                        raise core.DomainError('Document uploads are closed for this application.')
                evidence = workspace.read_payslip(request.files.get('document'))
            with db.tx() as conn:
                person = _candidate(conn, token)
                if action == 'upload':
                    if person['status'] not in {'docs_requested', 'docs_uploaded'}:
                        raise core.DomainError('Document uploads are closed for this application.')
                    identified, amount = evidence
                    conn.execute('UPDATE imported_enquiries SET document_received = 1, payslip_detected = ?, '
                                 'net_pay_cents = ? WHERE application_id = ?', (identified, amount, person['id']))
                    core.set_status(conn, person['id'], 'docs_uploaded')
                    if person['status'] == 'docs_requested':
                        core.notify(conn, property_id=person['property_id'], application_id=None,
                                    title='Payslip ready to review', body=f'{person["name"]} submitted a payslip.',
                                    now=core.now(conn))
                    flash('Payslip submitted. The owner will review your application.')
                elif action in {'book', 'cancel'}:
                    _change_booking(conn, person, action, request.form.get('slot_id', type=int))
                else:
                    abort(400)
        except core.DomainError as exc:
            flash(str(exc), 'error')
        return redirect(url_for('workspace.candidate', token=token))

    with db.tx() as conn:
        person = _candidate(conn, token)
        prop = property_or_404(conn, person['property_id'])
        booked, slots = None, []
        if person['calendar_access']:
            booked = conn.execute('SELECT * FROM slots WHERE booked_application_id = ?', (person['id'],)).fetchone()
            if not booked:
                slots = conn.execute('SELECT * FROM slots WHERE property_id = ? AND starts_at > ? '
                                     'AND booked_application_id IS NULL AND offer_application_id IS NULL ORDER BY starts_at',
                                     (prop['id'], core.now(conn).isoformat())).fetchall()
    return render_template('workspace_candidate.html', person=person, property=prop, booked=booked, slots=slots)
