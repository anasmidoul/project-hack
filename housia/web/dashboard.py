"""Owner dashboard: portfolio, viewings and recent notifications."""

from datetime import timedelta

from flask import Blueprint, render_template

from housia import core, db

bp = Blueprint('dashboard', __name__)


@bp.get('/')
def index():
    with db.tx() as conn:
        now = core.now(conn)
        properties = conn.execute('''
            SELECT p.*,
                   (SELECT COUNT(*) FROM imported_enquiries e WHERE e.property_id = p.id) AS enquiries,
                   (SELECT COUNT(*) FROM imported_enquiries e WHERE e.property_id = p.id
                    AND e.document_received = 1 AND e.decision IS NULL) AS to_review
              FROM properties p ORDER BY p.id
        ''').fetchall()
        upcoming = conn.execute('''
            SELECT s.*, p.title AS property_title, a.name AS applicant_name
              FROM slots s JOIN properties p ON p.id = s.property_id
              JOIN applications a ON a.id = s.booked_application_id
             WHERE s.starts_at > ? AND s.starts_at <= ? ORDER BY s.starts_at
        ''', (now.isoformat(), (now + timedelta(days=14)).isoformat())).fetchall()
        activity = conn.execute('SELECT * FROM notifications WHERE application_id IS NULL ORDER BY id DESC LIMIT 6').fetchall()
    return render_template('dashboard.html', properties=properties, upcoming_viewings=upcoming, activity=activity)
