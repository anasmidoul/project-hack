"""Route unit B1: dashboard blueprint (stub).

Contract: DESIGN.md section 9.
"""

from flask import Blueprint, flash, redirect, render_template

bp = Blueprint("dashboard", __name__)


@bp.get("/")
def index():
    # TODO(B1): context = properties, upcoming_viewings, activity
    return render_template(
        "dashboard.html",
        properties=[],
        upcoming_viewings=[],
        activity=[],
    )
