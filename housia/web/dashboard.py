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
    """Counts for the owner workspace (imported enquiries): enquiries, to_review."""
    row = conn.execute(
        "SELECT COUNT(*) AS enquiries, "
        "COALESCE(SUM(document_received = 1 AND decision IS NULL), 0) AS to_review "
        "FROM imported_enquiries WHERE property_id = ?",
        (property_id,),
    ).fetchone()
    return dict(row)
