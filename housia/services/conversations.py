"""Unit A3 — conversations: store portal conversations and messages.

Contract: DESIGN.md section 7 (conversations.py).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import TYPE_CHECKING

from housia.core import DomainError

if TYPE_CHECKING:
    from housia.channels.base import IncomingMessage

    Row = sqlite3.Row

CONVERSATION_STATUSES = ("open", "needs_landlord")
OUTGOING_STATUSES = ("draft", "approved")

# Message columns, minus external_id, for queries that put the conversation's external_id there.
_MESSAGE_COLS = ("m.id, m.conversation_id, m.direction, m.body, m.status, m.in_reply_to, "
                 "m.note, m.created_at, m.sent_at")


def _iso(value) -> str:
    if isinstance(value, datetime):
        return value.replace(microsecond=0).isoformat()
    return str(value)


def _get_message(conn, message_id) -> Row:
    row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    if row is None:
        raise DomainError("Message not found.")
    return row


def record_incoming(conn: sqlite3.Connection, channel: str, msg: IncomingMessage,
                    property_id: int, now: datetime) -> int | None:
    """Record an incoming message.

    Creates the conversation if new; returns the new message id, or None if already recorded.
    """
    conn.execute(
        "INSERT OR IGNORE INTO conversations (property_id, channel, external_id, contact_name, "
        "created_at) VALUES (?, ?, ?, ?, ?)",
        (property_id, channel, msg.external_conversation_id, msg.contact_name or "", _iso(now)),
    )
    conv = conn.execute(
        "SELECT id, contact_name FROM conversations WHERE channel = ? AND external_id = ?",
        (channel, msg.external_conversation_id),
    ).fetchone()
    if not conv["contact_name"] and msg.contact_name:
        conn.execute("UPDATE conversations SET contact_name = ? WHERE id = ?",
                     (msg.contact_name, conv["id"]))
    cur = conn.execute(
        "INSERT OR IGNORE INTO messages (conversation_id, direction, body, external_id, status, "
        "created_at) VALUES (?, 'in', ?, ?, 'received', ?)",
        (conv["id"], msg.text, msg.external_message_id, _iso(now)),
    )
    return cur.lastrowid if cur.rowcount == 1 else None


def get_conversation(conn: sqlite3.Connection, conversation_id: int) -> Row:
    """Return one conversation. A missing id raises DomainError."""
    row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    if row is None:
        raise DomainError("Conversation not found.")
    return row


def list_conversations(conn: sqlite3.Connection, property_id: int) -> list[dict]:
    """Return conversation columns + last_message, last_message_at, pending_drafts.

    Most recent activity first.
    """
    rows = conn.execute(
        """
        SELECT c.*,
               (SELECT body FROM messages WHERE conversation_id = c.id
                 ORDER BY created_at DESC, id DESC LIMIT 1) AS last_message,
               (SELECT created_at FROM messages WHERE conversation_id = c.id
                 ORDER BY created_at DESC, id DESC LIMIT 1) AS last_message_at,
               (SELECT COUNT(*) FROM messages WHERE conversation_id = c.id
                 AND status = 'draft') AS pending_drafts
          FROM conversations c
         WHERE c.property_id = ?
         ORDER BY COALESCE(last_message_at, c.created_at) DESC, c.id DESC
        """,
        (property_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_thread(conn: sqlite3.Connection, conversation_id: int) -> list[Row]:
    """Return the messages of a conversation, oldest first."""
    get_conversation(conn, conversation_id)
    return conn.execute(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at, id",
        (conversation_id,),
    ).fetchall()


def link_application(conn: sqlite3.Connection, conversation_id: int,
                     application_id: int) -> None:
    """Link a conversation to an application."""
    get_conversation(conn, conversation_id)
    conn.execute("UPDATE conversations SET application_id = ? WHERE id = ?",
                 (application_id, conversation_id))


def set_conversation_status(conn: sqlite3.Connection, conversation_id: int, status: str) -> None:
    """Set the conversation status ('open' | 'needs_landlord')."""
    if status not in CONVERSATION_STATUSES:
        raise DomainError(f"Unknown conversation status: {status}.")
    get_conversation(conn, conversation_id)
    conn.execute("UPDATE conversations SET status = ? WHERE id = ?", (status, conversation_id))


def save_outgoing(conn: sqlite3.Connection, conversation_id: int, body: str, status: str,
                  in_reply_to: int | None, note: str | None, now: datetime) -> int:
    """Save an outgoing message and return its id. status: 'draft' | 'approved'.

    At most one live reply per incoming message (index one_reply_per_incoming).
    """
    if status not in OUTGOING_STATUSES:
        raise DomainError(f"An outgoing message cannot be saved as {status}.")
    if not (body or "").strip():
        raise DomainError("The reply is empty.")
    get_conversation(conn, conversation_id)
    if in_reply_to is not None:
        incoming = _get_message(conn, in_reply_to)
        if incoming["conversation_id"] != conversation_id or incoming["direction"] != "in":
            raise DomainError("A reply must answer an incoming message of the same conversation.")
    try:
        cur = conn.execute(
            "INSERT INTO messages (conversation_id, direction, body, status, in_reply_to, note, "
            "created_at) VALUES (?, 'out', ?, ?, ?, ?, ?)",
            (conversation_id, body, status, in_reply_to, note, _iso(now)),
        )
    except sqlite3.IntegrityError as e:
        raise DomainError("This message already has a reply.") from e
    return cur.lastrowid


def approve(conn: sqlite3.Connection, message_id: int, body: str | None,
            now: datetime) -> None:
    """Approve a draft: draft -> approved; optional edited text."""
    msg = _get_message(conn, message_id)
    if msg["status"] != "draft":
        raise DomainError("Only a draft can be approved.")
    if body is not None and not body.strip():
        raise DomainError("The reply is empty.")
    conn.execute("UPDATE messages SET status = 'approved', body = ? WHERE id = ?",
                 (msg["body"] if body is None else body, message_id))


def discard(conn: sqlite3.Connection, message_id: int) -> None:
    """Discard a draft: draft -> discarded."""
    msg = _get_message(conn, message_id)
    if msg["status"] != "draft":
        raise DomainError("Only a draft can be discarded.")
    conn.execute("UPDATE messages SET status = 'discarded' WHERE id = ?", (message_id,))


def unanswered(conn: sqlite3.Connection, channel: str) -> list[Row]:
    """Return incoming messages that have no reply row at all, oldest first.

    A discarded draft still counts as a reply: discarding means the landlord takes over this
    message, so the worker must not write a new draft for it. The landlord can still answer it
    by hand later (the one_reply_per_incoming index ignores discarded rows).

    Message columns + property_id, contact_name, application_id, conversation_external_id.
    """
    return conn.execute(
        """
        SELECT m.*, c.property_id, c.contact_name, c.application_id,
               c.external_id AS conversation_external_id
          FROM messages m JOIN conversations c ON c.id = m.conversation_id
         WHERE c.channel = ? AND m.direction = 'in'
           AND NOT EXISTS (SELECT 1 FROM messages r WHERE r.in_reply_to = m.id)
         ORDER BY m.id
        """,
        (channel,),
    ).fetchall()


def pending_to_send(conn: sqlite3.Connection, channel: str) -> list[Row]:
    """Return approved outgoing messages + conversation external_id, oldest first.

    `external_id` is the conversation's id on the portal (outgoing messages have none).
    """
    return conn.execute(
        f"""
        SELECT {_MESSAGE_COLS}, c.external_id AS external_id, c.property_id
          FROM messages m JOIN conversations c ON c.id = m.conversation_id
         WHERE c.channel = ? AND m.direction = 'out' AND m.status = 'approved'
         ORDER BY m.id
        """,
        (channel,),
    ).fetchall()


def mark_sent(conn: sqlite3.Connection, message_id: int, now: datetime) -> None:
    """Mark an outgoing message as sent."""
    msg = _get_message(conn, message_id)
    if msg["status"] != "approved":
        raise DomainError("Only an approved message can be marked as sent.")
    conn.execute("UPDATE messages SET status = 'sent', sent_at = ? WHERE id = ?",
                 (_iso(now), message_id))


def mark_failed(conn: sqlite3.Connection, message_id: int, error: str) -> None:
    """Mark an outgoing message as failed, storing the error in note. Never resent automatically."""
    msg = _get_message(conn, message_id)
    if msg["status"] != "approved":
        raise DomainError("Only an approved message can be marked as failed.")
    conn.execute("UPDATE messages SET status = 'failed', note = ? WHERE id = ?",
                 (error, message_id))
