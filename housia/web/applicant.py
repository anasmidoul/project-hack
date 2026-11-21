"""Route unit B6: applicant blueprint (stub).

Contract: DESIGN.md section 9.
"""

from flask import Blueprint, flash, redirect, render_template

bp = Blueprint("applicant", __name__)


@bp.get("/apply/<int:property_id>")
def apply(property_id):
    # TODO(B6): context = property
    return render_template(
        "apply.html",
        property=None,
    )


@bp.get("/a/<token>")
def page(token):
    # TODO(B6): context = application, property, needs_details, demo_files, slots, notifications, is_finalist, contract_status
    return render_template(
        "applicant.html",
        application=None,
        property=None,
        needs_details=False,
        demo_files=[],
        slots=[],
        notifications=[],
        is_finalist=False,
        contract_status="",
    )


@bp.post("/apply/<int:property_id>")
def apply_submit(property_id):
    # TODO(B6): form fields = name, email, phone, preferences, availability (repeated)
    # NOTE: Real route redirects to /a/<token> on success.
    flash("Not implemented yet (B6).", "error")
    return redirect(f"/apply/{property_id}")


@bp.post("/a/<token>/details")
def details(token):
    # TODO(B6): form fields = name, email, phone, preferences, availability (repeated)
    flash("Not implemented yet (B6).", "error")
    return redirect(f"/a/{token}")


@bp.post("/a/<token>/document")
def document(token):
    # TODO(B6): form fields = file_name
    flash("Not implemented yet (B6).", "error")
    return redirect(f"/a/{token}")


@bp.post("/a/<token>/book")
def book(token):
    # TODO(B6): form fields = slot_id
    flash("Not implemented yet (B6).", "error")
    return redirect(f"/a/{token}")


@bp.post("/a/<token>/cancel")
def cancel(token):
    # TODO(B6): form fields = slot_id
    flash("Not implemented yet (B6).", "error")
    return redirect(f"/a/{token}")


@bp.post("/a/<token>/waitlist/join")
def waitlist_join(token):
    # TODO(B6): form fields = slot_id
    flash("Not implemented yet (B6).", "error")
    return redirect(f"/a/{token}")


@bp.post("/a/<token>/waitlist/leave")
def waitlist_leave(token):
    # TODO(B6): form fields = slot_id
    flash("Not implemented yet (B6).", "error")
    return redirect(f"/a/{token}")


@bp.post("/a/<token>/offer/accept")
def offer_accept(token):
    # TODO(B6): form fields = slot_id
    flash("Not implemented yet (B6).", "error")
    return redirect(f"/a/{token}")


@bp.post("/a/<token>/offer/decline")
def offer_decline(token):
    # TODO(B6): form fields = slot_id
    flash("Not implemented yet (B6).", "error")
    return redirect(f"/a/{token}")
