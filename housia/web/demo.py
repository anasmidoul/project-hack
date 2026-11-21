"""Route unit B7: demo blueprint (stub).

Contract: DESIGN.md section 9.
"""

from flask import Blueprint, flash, redirect, render_template

from housia import db

bp = Blueprint("demo", __name__)


@bp.get("/inbox")
def inbox():
    with db.tx() as conn:
        notifications = conn.execute(
            'SELECT * FROM notifications WHERE application_id IS NULL ORDER BY id DESC LIMIT 100'
        ).fetchall()
    return render_template('inbox.html', notifications=notifications)


@bp.get("/demo")
def page():
    # TODO(B7): context = applications, selected_token
    return render_template(
        "demo.html",
        applications=[],
        selected_token="",
    )


@bp.post("/inbox/read-all")
def read_all():
    with db.tx() as conn:
        conn.execute('UPDATE notifications SET is_read = 1 WHERE application_id IS NULL')
    return redirect("/inbox")


@bp.post("/demo/clock")
def clock():
    # TODO(B7): form fields = minutes
    flash("Not implemented yet (B7).", "error")
    return redirect("/demo")


@bp.post("/demo/reset")
def reset():
    # TODO(B7): form fields = none
    flash("Not implemented yet (B7).", "error")
    return redirect("/demo")
