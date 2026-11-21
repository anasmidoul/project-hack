"""Owner workflow integration: source tracking, private evidence and the built-in agenda."""

import io
import re
from datetime import timedelta

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from housia import config, core, db
from housia.services import workspace


def csrf(client, path, **kwargs):
    response = client.get(path, **kwargs)
    assert response.status_code == 200
    return re.search(rb'name="csrf_token" value="([^"]+)"', response.data)[1].decode()


def payslip(*lines):
    writer = PdfWriter()
    page = writer.add_blank_page(600, 800)
    name = NameObject
    page[name('/Resources')] = DictionaryObject({name('/Font'): DictionaryObject({name('/F1'): DictionaryObject({
        name('/Type'): name('/Font'), name('/Subtype'): name('/Type1'), name('/BaseFont'): name('/Helvetica')
    })})})
    stream = DecodedStreamObject()
    stream.set_data(('BT /F1 12 Tf 72 700 Td 16 TL ' + ' T* '.join(f'({line}) Tj' for line in lines) + ' ET').encode())
    page[name('/Contents')] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output


def add_property(client):
    token = csrf(client, '/properties/new')
    response = client.post('/properties', data={
        'csrf_token': token, 'title': 'Retiro apartment', 'address': 'Example Road 3',
        'city': 'Madrid', 'rent_eur': 1200, 'rental_type': 'residential', 'invite_limit': 2,
    })
    assert response.location == '/properties/1'
    return token


def import_people(client, token, channel, text):
    return client.post('/properties/1/workspace/import', data={
        'csrf_token': token, 'channel': channel, 'enquiries': (io.BytesIO(text.encode()), 'enquiries.csv')
    }, follow_redirects=True)


def test_owner_workflow_end_to_end(client):
    owner_csrf = add_property(client)
    base = '/properties/1'
    action = base + '/workspace'
    assert b'Import from Idealista' in client.get(base + '?step=import&channel=idealista').data
    assert b'name,thread_ref' in client.get('/workspace/import-template/fotocasa.csv').data
    csv = 'name,thread_ref\nInez Garcia,idealista-1\nInez Again,idealista-1\n'
    assert b'Imported: 1. Duplicates skipped: 1.' in import_people(client, owner_csrf, 'idealista', csv).data
    assert b'Imported: 0' in import_people(client, owner_csrf, 'idealista', csv).data
    assert b'Imported: 1' in import_people(client, owner_csrf, 'fotocasa', 'name;thread_ref\nFiona;idealista-1').data
    assert b'Imported: 1' in import_people(client, owner_csrf, 'whatsapp', 'name,thread_ref\nWill,+34 600 123 456').data
    inbox = client.get(base + '?step=reply').data
    assert b'Hi Inez, thanks' in inbox and b'Hi Will, thanks' in inbox
    assert b'https://wa.me/34600123456' in inbox and b'https://www.fotocasa.es/' in inbox
    with db.tx() as conn:
        applications = workspace.enquiries(conn, 1)
        person = next(row for row in applications if row['channel'] == 'idealista')
        fiona = next(row for row in applications if row['channel'] == 'fotocasa')
        starts = (core.now(conn) + timedelta(days=2)).replace(hour=15, minute=0)
    candidate = client.application.test_client()
    candidate_url = '/viewing/' + person['token']
    assert client.get('/viewing/unknown-token').status_code == 404
    candidate_csrf = csrf(candidate, candidate_url)
    assert candidate_url.encode() in inbox
    assert client.post(action + '/brief', data={'csrf_token': owner_csrf, 'min_net_eur': 2200}).status_code == 302
    assert b'must submit a payslip' in client.post(action + f'/enquiries/{person["id"]}/decision', data={
        'csrf_token': owner_csrf, 'decision': 'invite',
    }, follow_redirects=True).data
    upload = candidate.post(candidate_url, data={
        'csrf_token': candidate_csrf, 'action': 'upload',
        'document': (payslip('PAYSLIP', 'Private name, address and bank account', 'Net pay: 2.350,50 EUR'), 'latest.pdf'),
    }, follow_redirects=True)
    assert b'Payslip received' in upload.data
    assert upload.headers['Cache-Control'] == 'no-store'
    screened = client.get(base + '?step=screen&result=match').data
    assert b'Matches your screening brief' in screened and b'Inez Garcia' in screened and b'Fiona' not in screened
    assert b'2.350' not in screened and b'bank account' not in screened
    data = {'csrf_token': owner_csrf, 'starts_at': starts.strftime('%Y-%m-%dT%H:%M'), 'duration_min': 30}
    assert b'Viewing slot added' in client.post(action + '/slots', data=data, follow_redirects=True).data
    assert b'time overlaps' in client.post(action + '/slots', data=data, follow_redirects=True).data
    assert b'viewing link is now active' in client.post(action + f'/enquiries/{person["id"]}/decision', data={
        'csrf_token': owner_csrf, 'decision': 'invite',
    }, follow_redirects=True).data
    assert b'on Fotocasa' in client.post(action + f'/enquiries/{fiona["id"]}/decision', data={
        'csrf_token': owner_csrf, 'decision': 'decline',
    }, follow_redirects=True).data
    assert b'This application is closed' in candidate.get('/viewing/' + fiona['token']).data
    assert b'Choose a viewing time' in candidate.get(candidate_url).data
    with db.tx() as conn:
        slot_id = conn.execute('SELECT id FROM slots').fetchone()[0]
        assert conn.execute('SELECT net_pay_cents FROM imported_enquiries WHERE application_id=?', (person['id'],)).fetchone()[0] is None
    assert b'Viewing confirmed' in candidate.post(candidate_url, data={
        'csrf_token': candidate_csrf, 'action': 'book', 'slot_id': slot_id,
    }, follow_redirects=True).data
    agenda = client.get(base + '?step=agenda').data
    assert b'1 confirmed' in agenda and b'Inez Garcia' in agenda
    assert b'Your viewing was cancelled' in candidate.post(candidate_url, data={
        'csrf_token': candidate_csrf, 'action': 'cancel', 'slot_id': slot_id,
    }, follow_redirects=True).data
    assert b'0 confirmed' in client.get(base + '?step=agenda').data
    assert b'Viewing cancelled' in client.get('/inbox').data


def test_invalid_csv_is_atomic_and_csrf_is_required(client):
    token = add_property(client)
    assert b'Check line 3' in import_people(client, token, 'whatsapp', 'name,thread_ref\nFirst,+34600123456\nSecond,invalid').data
    with db.tx() as conn:
        assert not workspace.enquiries(conn, 1)
    assert client.post('/properties/1/workspace/brief', data={'min_net_eur': '1000'}).status_code == 400


def test_owner_password_does_not_block_private_applicant_links(client, monkeypatch):
    token = add_property(client)
    import_people(client, token, 'idealista', 'name,thread_ref\nFirst,reference-1')
    with db.tx() as conn:
        app_token = workspace.enquiries(conn, 1)[0]['token']
    monkeypatch.setattr(config, 'OWNER_PASSWORD', 'test-owner-password')
    assert client.get('/').status_code == 401
    assert client.get('/properties/1?step=reply').status_code == 401
    assert client.get('/', auth=('owner', config.OWNER_PASSWORD)).status_code == 200
    assert client.get('/viewing/' + app_token).status_code == 200


def test_ai_only_receives_outcome_category(monkeypatch):
    def model(system, user):
        assert user == 'Screening category: match.'
        return 'The payslip appears to meet the income criterion.'

    monkeypatch.setattr(config, 'WORKSPACE_AI_NOTES', True)
    monkeypatch.setattr(config, 'REPLY_MODEL', 'test')
    monkeypatch.setattr(config, 'OPENAI_API_KEY', 'test')
    monkeypatch.setattr(workspace.llm, '_call_model', model)
    assert workspace.ai_note('match') == 'The payslip appears to meet the income criterion.'


def test_amount_parsing_does_not_guess_ambiguous_separators():
    assert workspace.parse_net_pay('2.350,50 EUR') == 235050
    assert workspace.parse_net_pay('€2,350.50') == 235050
    assert workspace.parse_net_pay('2,350') is None
