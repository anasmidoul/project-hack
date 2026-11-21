"""Property setup for listings already published externally."""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from housia import core, db
from housia.web import workspace

bp = Blueprint('properties', __name__)


@bp.get('/properties/new')
@bp.get('/properties/<int:property_id>/edit')
def form(property_id=None):
    with db.tx() as conn:
        prop = workspace.property_or_404(conn, property_id) if property_id is not None else None
    return render_template('property_form.html', property=prop)


@bp.get('/properties/<int:property_id>')
def detail(property_id):
    step = request.args.get('step', 'import')
    if step not in workspace.STEPS:
        step = 'import'
    with db.tx() as conn:
        prop = workspace.property_or_404(conn, property_id)
        context = workspace.context(conn, prop, step)
    return render_template('property.html', property=prop, **context)


@bp.post('/properties')
@bp.post('/properties/<int:property_id>')
def save(property_id=None):
    title, address, city, listing_ref = [request.form.get(key, '').strip() for key in ('title', 'address', 'city', 'listing_ref')]
    try:
        rent = int(request.form.get('rent_eur', ''))
        rental_type = request.form.get('rental_type')
        invite_limit = int(request.form.get('invite_limit', '10'))
        if (not all(0 < len(text) <= 150 for text in (title, address, city))
                or len(listing_ref) > 300 or not 1 <= rent <= 1_000_000 or not 1 <= invite_limit <= 500
                or rental_type not in {'residential', 'temporary'}):
            raise ValueError
    except ValueError:
        flash('Check the property details, monthly rent and viewing invitation limit.', 'error')
        return redirect(url_for('properties.form', property_id=property_id))
    values = (title, address, city, rent, rental_type, listing_ref or None, invite_limit)
    with db.tx() as conn:
        if property_id is None:
            property_id = conn.execute(
                'INSERT INTO properties (title, address, city, rent_eur, rental_type, listing_ref, invite_limit, '
                'required_document, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (*values, 'Latest monthly payslip', core.now(conn).isoformat()),
            ).lastrowid
        else:
            workspace.property_or_404(conn, property_id)
            conn.execute('UPDATE properties SET title=?, address=?, city=?, rent_eur=?, rental_type=?, listing_ref=?, '
                         'invite_limit=? WHERE id=?', (*values, property_id))
    flash('Property saved.')
    return redirect(url_for('properties.detail', property_id=property_id))
