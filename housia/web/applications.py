"""Route unit B2: applications blueprint (stub).

Contract: DESIGN.md section 9.
"""

from flask import Blueprint, flash, redirect, render_template, request

from housia import core, db
from housia.services import applications, documents, properties

bp = Blueprint("applications", __name__)


@bp.get("/properties/<int:property_id>/applications")
def list_page(property_id):
    try:
        with db.tx() as conn:
            prop = properties.get_property(conn, property_id)
            rows = applications.list_for_property(conn, property_id)
    except core.DomainError as exc:
        flash(str(exc), "error")
        return redirect("/")
    return render_template(
        "applications.html",
        property=prop,
        applications=rows,
    )


@bp.get("/applications/<int:application_id>")
def detail(application_id):
    try:
        with db.tx() as conn:
            app = applications.get_application(conn, application_id)
            prop = properties.get_property(conn, app["property_id"])
            conversation = conn.execute(
                "SELECT * FROM conversations WHERE application_id=? ORDER BY id DESC LIMIT 1", (application_id,)
            ).fetchone()
    except core.DomainError as exc:
        flash(str(exc), "error")
        return redirect("/")
    return render_template(
        "application.html",
        application=app,
        property=prop,
        demo_files=documents.demo_files(),
        conversation=conversation,
    )


@bp.post("/properties/<int:property_id>/applications")
def create(property_id):
    try:
        data = {"name": request.form.get("name", ""), "email": request.form.get("email", ""),
                "phone": request.form.get("phone", ""), "preferences": request.form.get("preferences", ""),
                "availability": request.form.getlist("availability")}
        with db.tx() as conn:
            app_id = applications.create_application(conn, property_id, data, "phone", core.now(conn))
        flash("Application added.", "ok")
        return redirect(f"/applications/{app_id}")
    except core.DomainError as exc:
        flash(str(exc), "error")
    return redirect(f"/properties/{property_id}/applications")


@bp.post("/applications/<int:application_id>/document/request")
def document_request(application_id):
    _document_action(application_id, documents.request_document, "Document requested.")
    return redirect(f"/applications/{application_id}")


@bp.post("/applications/<int:application_id>/document/approve")
def document_approve(application_id):
    _document_action(application_id, documents.approve_document, "Document approved.")
    return redirect(f"/applications/{application_id}")


@bp.post("/applications/<int:application_id>/document/correction")
def document_correction(application_id):
    try:
        with db.tx() as conn:
            documents.request_correction(conn, application_id, request.form.get("note", ""), core.now(conn))
        flash("Correction requested.", "ok")
    except core.DomainError as exc:
        flash(str(exc), "error")
    return redirect(f"/applications/{application_id}")


@bp.post("/applications/<int:application_id>/calendar-access")
def calendar_access(application_id):
    try:
        with db.tx() as conn:
            core.grant_calendar_access(conn, application_id, "landlord", core.now(conn))
        flash("Calendar access granted.", "ok")
    except core.DomainError as exc:
        flash(str(exc), "error")
    return redirect(f"/applications/{application_id}")


def _document_action(application_id, service, success):
    try:
        with db.tx() as conn:
            service(conn, application_id, core.now(conn))
        flash(success, "ok")
    except core.DomainError as exc:
        flash(str(exc), "error")
