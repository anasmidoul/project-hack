"""Route unit A5: conversations blueprint (stub).

Contract: DESIGN.md section 9.
"""

from flask import Blueprint, flash, redirect, render_template

bp = Blueprint("conversations", __name__)


@bp.get("/properties/<int:property_id>/conversations")
def list_page(property_id):
    # TODO(A5): context = property, conversations
    return render_template(
        "conversations.html",
        property=None,
        conversations=[],
    )


@bp.get("/conversations/<int:conversation_id>")
def detail(conversation_id):
    # TODO(A5): context = conversation, property, messages, application
    return render_template(
        "conversation.html",
        conversation=None,
        property=None,
        messages=[],
        application=None,
    )


@bp.post("/messages/<int:message_id>/approve")
def approve(message_id):
    # TODO(A5): form fields = body (optional edited text)
    # NOTE: Redirect is '/' because the stub has no conversation id; the real route should redirect to /conversations/<conversation_id>.
    flash("Not implemented yet (A5).", "error")
    return redirect("/")


@bp.post("/messages/<int:message_id>/discard")
def discard(message_id):
    # TODO(A5): form fields = none
    # NOTE: Redirect is '/' because the stub has no conversation id; the real route should redirect to /conversations/<conversation_id>.
    flash("Not implemented yet (A5).", "error")
    return redirect("/")


@bp.post("/conversations/<int:conversation_id>/reply")
def reply(conversation_id):
    # TODO(A5): form fields = body
    flash("Not implemented yet (A5).", "error")
    return redirect(f"/conversations/{conversation_id}")


@bp.post("/worker/pause")
def worker_pause():
    # TODO(A5): form fields = paused (0 | 1)
    # NOTE: Redirect is '/' because the form lives in the top bar of every page; the real route may redirect back to the referring page.
    flash("Not implemented yet (A5).", "error")
    return redirect("/")
