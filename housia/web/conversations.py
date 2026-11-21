"""Route unit A5: conversations blueprint (landlord side of portal conversations).

Contract: DESIGN.md section 9.

The web app never sends a portal message. Approving or writing a reply only stores it as
`approved`; the worker sends it on its next loop.
"""

from flask import Blueprint, abort, flash, redirect, render_template, request

from housia import core, db
from housia.services import conversations

bp = Blueprint("conversations", __name__)


def _property(conn, property_id):
    # Direct SELECT: the properties service (B1) may still be a stub.
    row = conn.execute("SELECT * FROM properties WHERE id = ?", (property_id,)).fetchone()
    if row is None:
        abort(404)
    return row


def _message_or_404(conn, message_id):
    row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    if row is None:
        abort(404)
    return row


def _newest_unanswered_incoming(conn, conversation_id):
    """Id of the newest incoming message with no live (non-discarded) reply, or None."""
    row = conn.execute(
        """
        SELECT m.id FROM messages m
         WHERE m.conversation_id = ? AND m.direction = 'in'
           AND NOT EXISTS (SELECT 1 FROM messages r
                            WHERE r.in_reply_to = m.id AND r.status <> 'discarded')
         ORDER BY m.created_at DESC, m.id DESC LIMIT 1
        """,
        (conversation_id,),
    ).fetchone()
    return row["id"] if row else None


@bp.get("/properties/<int:property_id>/conversations")
def list_page(property_id):
    with db.tx() as conn:
        prop = _property(conn, property_id)
        rows = conversations.list_conversations(conn, property_id)
    return render_template("conversations.html", property=prop, conversations=rows)


@bp.get("/conversations/<int:conversation_id>")
def detail(conversation_id):
    with db.tx() as conn:
        try:
            conv = conversations.get_conversation(conn, conversation_id)
        except core.DomainError:
            abort(404)
        prop = _property(conn, conv["property_id"])
        messages = conversations.get_thread(conn, conversation_id)
        application = None
        if conv["application_id"] is not None:
            # Direct SELECT: the applications service (B2) may still be a stub.
            application = conn.execute("SELECT * FROM applications WHERE id = ?",
                                       (conv["application_id"],)).fetchone()
    return render_template("conversation.html", conversation=conv, property=prop,
                           messages=messages, application=application)


@bp.post("/messages/<int:message_id>/approve")
def approve(message_id):
    body = request.form.get("body")  # None = keep the draft text
    with db.tx() as conn:
        conversation_id = _message_or_404(conn, message_id)["conversation_id"]
    try:
        with db.tx() as conn:
            conversations.approve(conn, message_id, body, core.now(conn))
            conversations.set_conversation_status(conn, conversation_id, "open")
        flash("Reply approved. It will be sent on the next worker loop.", "ok")
    except core.DomainError as e:
        flash(str(e), "error")
    return redirect(f"/conversations/{conversation_id}")


@bp.post("/messages/<int:message_id>/discard")
def discard(message_id):
    with db.tx() as conn:
        conversation_id = _message_or_404(conn, message_id)["conversation_id"]
    try:
        with db.tx() as conn:
            conversations.discard(conn, message_id)
            conversations.set_conversation_status(conn, conversation_id, "open")
        flash("Draft discarded. No automatic reply will be sent for this message.", "ok")
    except core.DomainError as e:
        flash(str(e), "error")
    return redirect(f"/conversations/{conversation_id}")


@bp.post("/conversations/<int:conversation_id>/reply")
def reply(conversation_id):
    body = request.form.get("body", "").strip()
    try:
        if not body:
            raise core.DomainError("The reply is empty.")
        with db.tx() as conn:
            try:
                conversations.get_conversation(conn, conversation_id)
            except core.DomainError:
                abort(404)
            in_reply_to = _newest_unanswered_incoming(conn, conversation_id)
            conversations.save_outgoing(conn, conversation_id, body, "approved", in_reply_to,
                                        None, core.now(conn))
            conversations.set_conversation_status(conn, conversation_id, "open")
        flash("Reply saved. It will be sent on the next worker loop.", "ok")
    except core.DomainError as e:
        flash(str(e), "error")
    return redirect(f"/conversations/{conversation_id}")


@bp.post("/worker/pause")
def worker_pause():
    paused = request.form.get("paused", "")
    try:
        if paused not in ("0", "1"):
            raise core.DomainError("Invalid value for paused.")
        with db.tx() as conn:
            core.set_setting(conn, "worker_paused", paused)
        flash("Worker paused." if paused == "1" else "Worker resumed.", "ok")
    except core.DomainError as e:
        flash(str(e), "error")
    return redirect(request.referrer or "/")
