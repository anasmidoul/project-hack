"""Route unit B7: demo blueprint (stub).

Contract: DESIGN.md section 9.
"""

from flask import Blueprint, flash, redirect, render_template

bp = Blueprint("demo", __name__)


@bp.get("/inbox")
def inbox():
    # TODO(B7): context = notifications
    return render_template(
        "inbox.html",
        notifications=[],
    )


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
    # TODO(B7): form fields = none
    flash("Not implemented yet (B7).", "error")
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
