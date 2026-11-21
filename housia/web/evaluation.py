"""Route unit B3: evaluation blueprint (stub).

Contract: DESIGN.md section 9.
"""

from flask import Blueprint, flash, redirect, render_template

bp = Blueprint("evaluation", __name__)


@bp.get("/properties/<int:property_id>/evaluation")
def page(property_id):
    # TODO(B3): context = property, eligible_count, remaining, result, applications_by_id
    return render_template(
        "evaluation.html",
        property=None,
        eligible_count=0,
        remaining=0,
        result=None,
        applications_by_id={},
    )


@bp.post("/properties/<int:property_id>/evaluation")
def run(property_id):
    # TODO(B3): form fields = none
    # NOTE: Real version re-renders evaluation.html with `result` instead of redirecting.
    flash("Not implemented yet (B3).", "error")
    return redirect(f"/properties/{property_id}/evaluation")


@bp.post("/properties/<int:property_id>/evaluation/invite")
def invite(property_id):
    # TODO(B3): form fields = application_ids (repeated)
    flash("Not implemented yet (B3).", "error")
    return redirect(f"/properties/{property_id}/evaluation")
