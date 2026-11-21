"""Route unit A1: mock_inbox blueprint (stub).

Contract: DESIGN.md section 9.
"""

from flask import Blueprint, flash, redirect, render_template

bp = Blueprint("mock_inbox", __name__)


@bp.get("/mock/inbox")
def inbox():
    # TODO(A1): context = threads
    return render_template(
        "mock_inbox.html",
        threads=[],
    )


@bp.get("/mock/inbox/<int:thread_id>")
def thread(thread_id):
    # TODO(A1): context = thread, messages
    return render_template(
        "mock_thread.html",
        thread=None,
        messages=[],
    )


@bp.post("/mock/inbox/<int:thread_id>/send")
def thread_send(thread_id):
    # TODO(A1): form fields = body
    flash("Not implemented yet (A1).", "error")
    return redirect(f"/mock/inbox/{thread_id}")


@bp.get("/mock/candidate")
def candidate():
    # TODO(A1): context = threads
    return render_template(
        "mock_candidate.html",
        threads=[],
    )


@bp.post("/mock/candidate/send")
def candidate_send():
    # TODO(A1): form fields = thread_id (empty = new thread), contact_name, body
    flash("Not implemented yet (A1).", "error")
    return redirect("/mock/candidate")
