"""Route unit B2: applications blueprint (stub).

Contract: DESIGN.md section 9.
"""

from flask import Blueprint, flash, redirect, render_template, request

from housia import core, db
from housia.services import applications, conversations, decisions, documents, properties

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


@bp.post("/applications/<int:application_id>/accept")
def accept(application_id):
    _send_decision(application_id, "accept")
    return redirect(f"/applications/{application_id}")


@bp.post("/applications/<int:application_id>/decline")
def decline(application_id):
    _send_decision(application_id, "decline")
    return redirect(f"/applications/{application_id}")


def _send_decision(application_id, kind):
    """Check, write the message with no transaction open (it may call the model), then apply the
    decision, queue the message for the worker and notify, all in one transaction."""
    try:
        with db.tx() as conn:
            app, prop = decisions.check(conn, application_id, kind)
        link = core.applicant_url(app["token"]) if kind == "accept" else None
        body = decisions.write_message(kind, prop, app, link)
        with db.tx() as conn:
            now = core.now(conn)
            if kind == "accept":
                decisions.accept(conn, application_id, now)
            else:
                decisions.decline(conn, application_id, now)
            conversation = conn.execute(
                "SELECT id FROM conversations WHERE application_id=? ORDER BY id DESC LIMIT 1", (application_id,)
            ).fetchone()
            if conversation is not None:
                conversations.save_outgoing(conn, conversation["id"], body, "approved", None, None, now)
            core.notify(conn, property_id=prop["id"], application_id=application_id,
                        title=decisions.MESSAGE_TITLE, body=body, now=now)
            what = "Acceptance" if kind == "accept" else "Decline"
            where = "queued for the portal and shown" if conversation is not None else "shown"
            result = "invited to a viewing" if kind == "accept" else "application closed"
            core.notify(conn, property_id=prop["id"], application_id=None,
                        title=f"{what} sent to {app['name']}",
                        body=f"{result.capitalize()}. The message was {where} on their applicant page.",
                        now=now)
        flash(f"{what} sent.", "ok")
    except core.DomainError as exc:
        flash(str(exc), "error")


def _document_action(application_id, service, success):
    try:
        with db.tx() as conn:
            service(conn, application_id, core.now(conn))
        flash(success, "ok")
    except core.DomainError as exc:
        flash(str(exc), "error")
