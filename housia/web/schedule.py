"""Route unit B4: schedule blueprint (stub).

Contract: DESIGN.md section 9.
"""

from flask import Blueprint, flash, redirect, render_template

bp = Blueprint("schedule", __name__)


@bp.get("/properties/<int:property_id>/schedule")
def page(property_id):
    # TODO(B4): context = property, slots
    return render_template(
        "schedule.html",
        property=None,
        slots=[],
    )


@bp.post("/properties/<int:property_id>/slots")
def create_slot(property_id):
    # TODO(B4): form fields = date (YYYY-MM-DD), time (HH:MM), duration_min
    flash("Not implemented yet (B4).", "error")
    return redirect(f"/properties/{property_id}/schedule")


@bp.post("/slots/<int:slot_id>/delete")
def delete_slot(slot_id):
    # TODO(B4): form fields = none
    # NOTE: Redirect is '/' because the stub has no property id; the real route should redirect to /properties/<property_id>/schedule.
    flash("Not implemented yet (B4).", "error")
    return redirect("/")


@bp.post("/slots/<int:slot_id>/cancel")
def cancel_slot(slot_id):
    # TODO(B4): form fields = none
    # NOTE: Redirect is '/' because the stub has no property id; the real route should redirect to /properties/<property_id>/schedule.
    flash("Not implemented yet (B4).", "error")
    return redirect("/")
