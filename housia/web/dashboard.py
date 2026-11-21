"""Route unit B1: dashboard blueprint (stub).

Contract: DESIGN.md section 9.
"""

from flask import Blueprint, render_template

from housia import core, db
from housia.services import properties

bp = Blueprint("dashboard", __name__)


@bp.get("/")
def index():
    with db.tx() as conn:
        rows = properties.list_properties(conn)
        listed = [
            {
                **dict(row),
                "stats": properties.property_stats(conn, row["id"]),
                **_workspace_counts(conn, row["id"]),
            }
            for row in rows
        ]
        viewings = properties.upcoming_viewings(conn, core.now(conn))
        activity = conn.execute(
            "SELECT * FROM notifications WHERE application_id IS NULL ORDER BY created_at DESC,id DESC LIMIT 10"
        ).fetchall()
    return render_template(
        "dashboard.html",
        properties=listed,
        upcoming_viewings=viewings,
        activity=activity,
    )


def _workspace_counts(conn, property_id):
    """Counts on a property card.

    enquiries: every applicant of the property, whatever the channel (portal message, public
    link, phone, imported list).
    to_review: what is waiting for the landlord: documents uploaded and not yet reviewed
    (including imported enquiries without a decision), plus conversations with a reply that
    needs approval.
    """
    enquiries = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE property_id = ?", (property_id,)
    ).fetchone()[0]
    documents = conn.execute(
        "SELECT COUNT(*) FROM applications a WHERE a.property_id = ? AND ("
        " a.status = 'docs_uploaded' OR EXISTS ("
        "  SELECT 1 FROM imported_enquiries i WHERE i.application_id = a.id"
        "  AND i.document_received = 1 AND i.decision IS NULL AND a.status <> 'closed'))",
        (property_id,),
    ).fetchone()[0]
    replies = conn.execute(
        "SELECT COUNT(*) FROM conversations c WHERE c.property_id = ? AND ("
        " c.status = 'needs_landlord' OR EXISTS ("
        "  SELECT 1 FROM messages m WHERE m.conversation_id = c.id"
        "  AND m.direction = 'out' AND m.status = 'draft'))",
        (property_id,),
    ).fetchone()[0]
    return {"enquiries": enquiries, "to_review": documents + replies}
