"""Route unit B2: applications blueprint (stub).

Contract: DESIGN.md section 9.
"""

from flask import Blueprint, flash, redirect, render_template

bp = Blueprint("applications", __name__)


@bp.get("/properties/<int:property_id>/applications")
def list_page(property_id):
    # TODO(B2): context = property, applications
    return render_template(
        "applications.html",
        property=None,
        applications=[],
    )


@bp.get("/applications/<int:application_id>")
def detail(application_id):
    # TODO(B2): context = application, property, demo_files, conversation
    return render_template(
        "application.html",
        application=None,
        property=None,
        demo_files=[],
        conversation=None,
    )


@bp.post("/properties/<int:property_id>/applications")
def create(property_id):
    # TODO(B2): form fields = name, email, phone, preferences, availability (repeated)
    flash("Not implemented yet (B2).", "error")
    return redirect(f"/properties/{property_id}/applications")


@bp.post("/applications/<int:application_id>/document/request")
def document_request(application_id):
    # TODO(B2): form fields = none
    flash("Not implemented yet (B2).", "error")
    return redirect(f"/applications/{application_id}")


@bp.post("/applications/<int:application_id>/document/approve")
def document_approve(application_id):
    # TODO(B2): form fields = none
    flash("Not implemented yet (B2).", "error")
    return redirect(f"/applications/{application_id}")


@bp.post("/applications/<int:application_id>/document/correction")
def document_correction(application_id):
    # TODO(B2): form fields = note
    flash("Not implemented yet (B2).", "error")
    return redirect(f"/applications/{application_id}")


@bp.post("/applications/<int:application_id>/calendar-access")
def calendar_access(application_id):
    # TODO(B2): form fields = none
    flash("Not implemented yet (B2).", "error")
    return redirect(f"/applications/{application_id}")
