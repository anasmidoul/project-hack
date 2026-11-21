"""Route unit B3: evaluation blueprint (stub).

Contract: DESIGN.md section 9.
"""

from flask import Blueprint, flash, redirect, render_template, request

from housia import core, db
from housia.services import applications, evaluation, properties

bp = Blueprint("evaluation", __name__)


@bp.get("/properties/<int:property_id>/evaluation")
def page(property_id):
    with db.tx() as conn:
        prop = properties.get_property(conn, property_id)
        eligible_count = conn.execute(
            "SELECT COUNT(*) FROM applications WHERE property_id = ? AND status = 'docs_approved'",
            (property_id,),
        ).fetchone()[0]
        remaining = max(0, prop["invite_limit"] - core.invited_count(conn, property_id))
        by_id = {row["id"]: row for row in applications.list_for_property(conn, property_id)}
        result = None
    return render_template("evaluation.html", property=prop, eligible_count=eligible_count,
                           remaining=remaining, result=result, applications_by_id=by_id)


@bp.post("/properties/<int:property_id>/evaluation")
def run(property_id):
    try:
        with db.tx() as conn:
            prop = properties.get_property(conn, property_id)
            result = evaluation.evaluate(conn, property_id, core.now(conn))
            eligible_count = conn.execute(
                "SELECT COUNT(*) FROM applications WHERE property_id = ? AND status = 'docs_approved'",
                (property_id,),
            ).fetchone()[0]
            remaining = result.remaining
            by_id = {row["id"]: row for row in applications.list_for_property(conn, property_id)}
        return render_template("evaluation.html", property=prop, eligible_count=eligible_count,
                               remaining=remaining, result=result, applications_by_id=by_id)
    except core.DomainError as exc:
        flash(str(exc), "error")
        return redirect(f"/properties/{property_id}/evaluation")


@bp.post("/properties/<int:property_id>/evaluation/invite")
def invite(property_id):
    try:
        application_ids = [int(value) for value in request.form.getlist("application_ids")]
        with db.tx() as conn:
            evaluation.invite(conn, property_id, application_ids, core.now(conn))
        flash("Selected applicants were invited.", "ok")
    except (core.DomainError, ValueError) as exc:
        flash(str(exc) if isinstance(exc, core.DomainError) else "Choose valid applicants.", "error")
    return redirect(f"/properties/{property_id}/evaluation")
