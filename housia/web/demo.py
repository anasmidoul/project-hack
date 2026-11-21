"""Route unit B7: demo blueprint (stub).

Contract: DESIGN.md section 9.
"""

from flask import Blueprint, flash, redirect, render_template, request

from housia import back_url, core, db

bp = Blueprint("demo", __name__)


@bp.get("/inbox")
def inbox():
    with db.tx() as conn:
        notifications = conn.execute(
            "SELECT n.*, COALESCE(a.name,'Landlord') AS recipient_name "
            "FROM notifications n LEFT JOIN applications a ON a.id=n.application_id "
            "ORDER BY n.created_at DESC,n.id DESC"
        ).fetchall()
    return render_template(
        "inbox.html",
        notifications=notifications,
    )


@bp.get("/demo")
def page():
    """The old demo room. Its tools (clock, reset) are on the guide now; old links go there."""
    return redirect("/guide")


@bp.post("/inbox/read-all")
def read_all():
    with db.tx() as conn:
        conn.execute("UPDATE notifications SET is_read=1 WHERE application_id IS NULL")
    flash("Landlord notifications marked as read.", "ok")
    return redirect(back_url("/guide"))


@bp.post("/demo/clock")
def clock():
    try:
        minutes = int(request.form.get("minutes", ""))
        if not -1440 <= minutes <= 1440:
            raise ValueError
        with db.tx() as conn:
            offset = int(core.get_setting(conn, "clock_offset_min", "0") or 0)
            core.set_setting(conn, "clock_offset_min", offset + minutes)
        flash(f"Demo clock advanced by {minutes} minutes.", "ok")
    except ValueError:
        flash("Enter a whole number of minutes between -1440 and 1440.", "error")
    return redirect(back_url("/guide"))


@bp.post("/demo/reset")
def reset():
    db.reset_db()
    flash("Demo data reset.", "ok")
    return redirect(back_url("/guide"))
