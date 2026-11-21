"""Route unit B5: contract blueprint (stub).

Contract: DESIGN.md section 9.
"""

from flask import Blueprint, flash, redirect, render_template

bp = Blueprint("contract", __name__)


@bp.get("/properties/<int:property_id>/contract")
def page(property_id):
    # TODO(B5): context = property, attended, finalist, contract_files
    return render_template(
        "contract.html",
        property=None,
        attended=[],
        finalist=None,
        contract_files=[],
    )


@bp.post("/slots/<int:slot_id>/attendance")
def attendance(slot_id):
    # TODO(B5): form fields = value (attended | absent)
    # NOTE: Redirect is '/' because the stub has no property id; the real route should redirect to the page the form lives on (/properties/<property_id>/schedule or /contract).
    flash("Not implemented yet (B5).", "error")
    return redirect("/")


@bp.post("/properties/<int:property_id>/finalist")
def finalist(property_id):
    # TODO(B5): form fields = application_id
    flash("Not implemented yet (B5).", "error")
    return redirect(f"/properties/{property_id}/contract")


@bp.post("/properties/<int:property_id>/contract/status")
def status(property_id):
    # TODO(B5): form fields = status (pending | sent)
    flash("Not implemented yet (B5).", "error")
    return redirect(f"/properties/{property_id}/contract")


@bp.post("/properties/<int:property_id>/contract/sign")
def sign(property_id):
    # TODO(B5): form fields = file_name
    flash("Not implemented yet (B5).", "error")
    return redirect(f"/properties/{property_id}/contract")
