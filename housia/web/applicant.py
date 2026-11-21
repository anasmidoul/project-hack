"""Route unit B6: applicant blueprint (stub).

Contract: DESIGN.md section 9.
"""

from flask import Blueprint, flash, redirect, render_template, request

from housia import core, db
from housia.services import applications, contracts, documents, properties, scheduling

bp = Blueprint("applicant", __name__)


@bp.get("/apply/<int:property_id>")
def apply(property_id):
    try:
        with db.tx() as conn:
            prop = properties.get_property(conn, property_id)
    except core.DomainError as exc:
        flash(str(exc), "error")
        return redirect("/")
    return render_template(
        "apply.html",
        property=prop,
    )


@bp.get("/a/<token>")
def page(token):
    try:
        with db.tx() as conn:
            app = applications.get_by_token(conn, token)
            prop = properties.get_property(conn, app["property_id"])
            slots = scheduling.slots_for_applicant(conn, app["id"], core.now(conn)) if app["calendar_access"] else []
            notifications = conn.execute(
                "SELECT * FROM notifications WHERE application_id=? ORDER BY created_at DESC,id DESC",
                (app["id"],),
            ).fetchall()
            is_finalist = prop["finalist_application_id"] == app["id"]
    except core.DomainError as exc:
        flash(str(exc), "error")
        return redirect("/")
    return render_template(
        "applicant.html",
        application=app,
        property=prop,
        needs_details=not bool(app["email"] and app["phone"]),
        demo_files=documents.demo_files(),
        slots=slots,
        notifications=notifications,
        is_finalist=is_finalist,
        contract_status=prop["contract_status"],
    )


@bp.post("/apply/<int:property_id>")
def apply_submit(property_id):
    try:
        with db.tx() as conn:
            app_id = applications.create_application(conn, property_id, _details_form(), "link", core.now(conn))
            token = applications.get_application(conn, app_id)["token"]
        return redirect(f"/a/{token}")
    except core.DomainError as exc:
        flash(str(exc), "error")
    return redirect(f"/apply/{property_id}")


@bp.post("/a/<token>/details")
def details(token):
    try:
        with db.tx() as conn:
            app = applications.get_by_token(conn, token)
            applications.update_details(conn, app["id"], _details_form())
        flash("Your details were saved.", "ok")
    except core.DomainError as exc:
        flash(str(exc), "error")
    return redirect(f"/a/{token}")


@bp.post("/a/<token>/document")
def document(token):
    application_id = None
    try:
        with db.tx() as conn:
            app = applications.get_by_token(conn, token)
            application_id = app["id"]
            documents.upload_document(conn, app["id"], request.form.get("file_name", ""), core.now(conn))
        from housia.services import doc_summary
        try:
            doc_summary.summarize_for_landlord(application_id)
        except NotImplementedError:
            pass  # A8 may still be a stub while Backend 2 is being built.
        flash("Document submitted.", "ok")
    except core.DomainError as exc:
        flash(str(exc), "error")
    return redirect(f"/a/{token}")


@bp.post("/a/<token>/book")
def book(token):
    _slot_action(token, lambda conn, app, slot, now: scheduling.book(conn, app["id"], slot, now),
                 "Viewing booked.")
    return redirect(f"/a/{token}")


@bp.post("/a/<token>/cancel")
def cancel(token):
    _slot_action(token, lambda conn, app, slot, now: _cancel_for_applicant(conn, app, slot, now),
                 "Viewing cancelled.")
    return redirect(f"/a/{token}")


@bp.post("/a/<token>/waitlist/join")
def waitlist_join(token):
    _slot_action(token, lambda conn, app, slot, now: scheduling.join_waitlist(conn, app["id"], slot, now),
                 "You joined the waiting list.")
    return redirect(f"/a/{token}")


@bp.post("/a/<token>/waitlist/leave")
def waitlist_leave(token):
    _slot_action(token, lambda conn, app, slot, now: scheduling.leave_waitlist(conn, app["id"], slot, now),
                 "You left the waiting list.")
    return redirect(f"/a/{token}")


@bp.post("/a/<token>/offer/accept")
def offer_accept(token):
    _slot_action(token, lambda conn, app, slot, now: scheduling.accept_offer(conn, app["id"], slot, now),
                 "Viewing offer accepted.")
    return redirect(f"/a/{token}")


@bp.post("/a/<token>/offer/decline")
def offer_decline(token):
    _slot_action(token, lambda conn, app, slot, now: scheduling.decline_offer(conn, app["id"], slot, now),
                 "Viewing offer declined.")
    return redirect(f"/a/{token}")


def _details_form():
    return {
        "name": request.form.get("name", ""), "email": request.form.get("email", ""),
        "phone": request.form.get("phone", ""), "preferences": request.form.get("preferences", ""),
        "availability": request.form.getlist("availability"),
    }


def _slot_action(token, action, success):
    try:
        slot_id = int(request.form["slot_id"])
        with db.tx() as conn:
            app = applications.get_by_token(conn, token)
            action(conn, app, slot_id, core.now(conn))
        flash(success, "ok")
    except (core.DomainError, KeyError, ValueError) as exc:
        flash(str(exc) if isinstance(exc, core.DomainError) else "Choose a valid viewing slot.", "error")


def _cancel_for_applicant(conn, app, slot_id, now):
    slot = conn.execute("SELECT booked_application_id FROM slots WHERE id=?", (slot_id,)).fetchone()
    if slot is None or slot["booked_application_id"] != app["id"]:
        raise core.DomainError("This viewing is not booked by you.")
    scheduling.cancel_booking(conn, slot_id, "applicant", now)
