"""Route unit B1: properties blueprint (stub).

Contract: DESIGN.md section 9.
"""

from flask import Blueprint, flash, redirect, render_template, request

from housia import core, db
from housia.services import properties
from housia.web import workspace

bp = Blueprint("properties", __name__)


@bp.get("/properties/new")
@bp.get("/properties/<int:property_id>/edit")
def form(property_id=None):
    try:
        with db.tx() as conn:
            prop = properties.get_property(conn, property_id) if property_id is not None else None
    except core.DomainError as exc:
        flash(str(exc), "error")
        return redirect("/")
    return render_template(
        "property_form.html",
        property=prop,
    )


@bp.get("/properties/<int:property_id>")
def detail(property_id):
    step = request.args.get("step", "import")
    if step not in workspace.STEPS:
        step = "import"
    try:
        with db.tx() as conn:
            prop = properties.get_property(conn, property_id)
            stats = properties.property_stats(conn, property_id)
            link = properties.public_link(property_id)
            messages = properties.copy_messages(prop, link)
            # Owner workspace (imported enquiries): step, steps, people, minimum, slots, channels, ...
            workspace_context = workspace.context(conn, prop, step)
    except core.DomainError as exc:
        flash(str(exc), "error")
        return redirect("/")
    return render_template(
        "property.html",
        property=prop,
        stats=stats,
        public_link=link,
        copy_messages=messages,
        **workspace_context,
    )


@bp.post("/properties")
def create():
    try:
        with db.tx() as conn:
            property_id = properties.create_property(conn, request.form, core.now(conn))
        flash("Property created.", "ok")
        return redirect(f"/properties/{property_id}")
    except core.DomainError as exc:
        flash(str(exc), "error")
        return redirect("/properties/new")


@bp.post("/properties/<int:property_id>")
def update(property_id):
    try:
        with db.tx() as conn:
            properties.update_property(conn, property_id, request.form)
        flash("Property updated.", "ok")
        return redirect(f"/properties/{property_id}")
    except core.DomainError as exc:
        flash(str(exc), "error")
    return redirect(f"/properties/{property_id}/edit")
