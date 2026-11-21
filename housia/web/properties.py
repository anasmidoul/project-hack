"""Route unit B1: properties blueprint (stub).

Contract: DESIGN.md section 9.
"""

from flask import Blueprint, flash, redirect, render_template

bp = Blueprint("properties", __name__)


@bp.get("/properties/new")
@bp.get("/properties/<int:property_id>/edit")
def form(property_id=None):
    # TODO(B1): context = property
    return render_template(
        "property_form.html",
        property=None,
    )


@bp.get("/properties/<int:property_id>")
def detail(property_id):
    # TODO(B1): context = property, stats, public_link, copy_messages
    return render_template(
        "property.html",
        property=None,
        stats=None,
        public_link="",
        copy_messages={},
    )


@bp.post("/properties")
def create():
    # TODO(B1): form fields = title, address, city, rental_type, rent_eur, description, facts, required_document, eval_mode, invite_limit, reply_mode, listing_ref
    flash("Not implemented yet (B1).", "error")
    return redirect("/properties/new")


@bp.post("/properties/<int:property_id>")
def update(property_id):
    # TODO(B1): form fields = title, address, city, rental_type, rent_eur, description, facts, required_document, eval_mode, invite_limit, reply_mode, listing_ref
    flash("Not implemented yet (B1).", "error")
    return redirect(f"/properties/{property_id}/edit")
