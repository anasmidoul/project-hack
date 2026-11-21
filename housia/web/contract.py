"""Route unit B5: contract blueprint (stub).

Contract: DESIGN.md section 9.
"""

from flask import Blueprint, flash, redirect, render_template, request

from housia import core, db
from housia.services import contracts, postviewing, properties

bp = Blueprint("contract", __name__)


@bp.get("/properties/<int:property_id>/contract")
def page(property_id):
    with db.tx() as conn:
        prop = properties.get_property(conn, property_id)
        attended = postviewing.attended_applications(conn, property_id)
        finalist = next((row for row in attended if row["id"] == prop["finalist_application_id"]), None)
    return render_template("contract.html", property=prop, attended=attended,
                           finalist=finalist, contract_files=contracts.demo_contract_files())


@bp.post("/slots/<int:slot_id>/attendance")
def attendance(slot_id):
    try:
        value = request.form.get("value", "")
        with db.tx() as conn:
            slot = conn.execute("SELECT property_id FROM slots WHERE id = ?", (slot_id,)).fetchone()
            if slot is None:
                raise core.DomainError("Viewing slot not found.")
            postviewing.set_attendance(conn, slot_id, value, core.now(conn))
            property_id = slot["property_id"]
        flash("Attendance recorded.", "ok")
        return redirect(f"/properties/{property_id}/schedule")
    except core.DomainError as exc:
        flash(str(exc), "error")
        return redirect("/")


@bp.post("/properties/<int:property_id>/finalist")
def finalist(property_id):
    try:
        application_id = int(request.form["application_id"])
        with db.tx() as conn:
            postviewing.select_finalist(conn, property_id, application_id, core.now(conn))
        flash("Final candidate selected.", "ok")
    except (core.DomainError, KeyError, ValueError) as exc:
        flash(str(exc) if isinstance(exc, core.DomainError) else "Choose a valid applicant.", "error")
    return redirect(f"/properties/{property_id}/contract")


@bp.post("/properties/<int:property_id>/contract/status")
def status(property_id):
    try:
        with db.tx() as conn:
            contracts.set_contract_status(conn, property_id, request.form.get("status", ""), core.now(conn))
        flash("Contract status updated.", "ok")
    except core.DomainError as exc:
        flash(str(exc), "error")
    return redirect(f"/properties/{property_id}/contract")


@bp.post("/properties/<int:property_id>/contract/sign")
def sign(property_id):
    try:
        with db.tx() as conn:
            contracts.attach_signed(conn, property_id, request.form.get("file_name", ""), core.now(conn))
        flash("Signed contract attached.", "ok")
    except core.DomainError as exc:
        flash(str(exc), "error")
    return redirect(f"/properties/{property_id}/contract")
