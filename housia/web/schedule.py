"""Route unit B4: schedule blueprint (stub).

Contract: DESIGN.md section 9.
"""

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request

from housia import core, db
from housia.services import properties, scheduling

bp = Blueprint("schedule", __name__)


@bp.get("/properties/<int:property_id>/schedule")
def page(property_id):
    try:
        with db.tx() as conn:
            prop = properties.get_property(conn, property_id)
            slots = scheduling.list_slots(conn, property_id)
    except core.DomainError as exc:
        flash(str(exc), "error")
        return redirect("/")
    return render_template(
        "schedule.html",
        property=prop,
        slots=slots,
    )


@bp.post("/properties/<int:property_id>/slots")
def create_slot(property_id):
    try:
        starts_at = datetime.strptime(f"{request.form['date']} {request.form['time']}", "%Y-%m-%d %H:%M")
        duration = int(request.form.get("duration_min", "30"))
        with db.tx() as conn:
            scheduling.create_slot(conn, property_id, starts_at, duration, core.now(conn))
        flash("Viewing slot created.", "ok")
    except (core.DomainError, KeyError, ValueError) as exc:
        flash(str(exc) if isinstance(exc, core.DomainError) else "Enter a valid date, time and duration.", "error")
    return redirect(f"/properties/{property_id}/schedule")


@bp.post("/slots/<int:slot_id>/delete")
def delete_slot(slot_id):
    try:
        with db.tx() as conn:
            slot = conn.execute("SELECT property_id FROM slots WHERE id=?", (slot_id,)).fetchone()
            if slot is None:
                raise core.DomainError("Viewing slot not found.")
            property_id = slot["property_id"]
            scheduling.delete_slot(conn, slot_id)
        flash("Viewing slot deleted.", "ok")
    except core.DomainError as exc:
        flash(str(exc), "error")
        if "property_id" not in locals():
            return redirect("/")
    return redirect(f"/properties/{property_id}/schedule")


@bp.post("/slots/<int:slot_id>/cancel")
def cancel_slot(slot_id):
    try:
        with db.tx() as conn:
            slot = conn.execute("SELECT property_id FROM slots WHERE id=?", (slot_id,)).fetchone()
            if slot is None:
                raise core.DomainError("Viewing slot not found.")
            property_id = slot["property_id"]
            scheduling.cancel_booking(conn, slot_id, "landlord", core.now(conn))
        flash("Viewing cancelled.", "ok")
    except core.DomainError as exc:
        flash(str(exc), "error")
        if "property_id" not in locals():
            return redirect("/")
    return redirect(f"/properties/{property_id}/schedule")
