"""Unit A3 — conversations: store portal conversations and messages.

Contract: DESIGN.md section 7 (conversations.py).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3
    from datetime import datetime

    from housia.channels.base import IncomingMessage

    Row = sqlite3.Row


def record_incoming(conn: sqlite3.Connection, channel: str, msg: IncomingMessage,
                    property_id: int, now: datetime) -> int | None:
    """Record an incoming message.

    Creates the conversation if new; returns the new message id, or None if already recorded.
    """
    raise NotImplementedError("A3: conversations.record_incoming")


def get_conversation(conn: sqlite3.Connection, conversation_id: int) -> Row:
    """Return one conversation. A missing id raises DomainError."""
    raise NotImplementedError("A3: conversations.get_conversation")


def list_conversations(conn: sqlite3.Connection, property_id: int) -> list[dict]:
    """Return conversation columns + last_message, pending_drafts."""
    raise NotImplementedError("A3: conversations.list_conversations")


def get_thread(conn: sqlite3.Connection, conversation_id: int) -> list[Row]:
    """Return the messages of a conversation, oldest first."""
    raise NotImplementedError("A3: conversations.get_thread")


def link_application(conn: sqlite3.Connection, conversation_id: int,
                     application_id: int) -> None:
    """Link a conversation to an application."""
    raise NotImplementedError("A3: conversations.link_application")


def set_conversation_status(conn: sqlite3.Connection, conversation_id: int, status: str) -> None:
    """Set the conversation status ('open' | 'needs_landlord')."""
    raise NotImplementedError("A3: conversations.set_conversation_status")


def save_outgoing(conn: sqlite3.Connection, conversation_id: int, body: str, status: str,
                  in_reply_to: int | None, note: str | None, now: datetime) -> int:
    """Save an outgoing message and return its id. status: 'draft' | 'approved'.

    At most one live reply per incoming message (index one_reply_per_incoming).
    """
    raise NotImplementedError("A3: conversations.save_outgoing")


def approve(conn: sqlite3.Connection, message_id: int, body: str | None,
            now: datetime) -> None:
    """Approve a draft: draft -> approved; optional edited text."""
    raise NotImplementedError("A3: conversations.approve")


def discard(conn: sqlite3.Connection, message_id: int) -> None:
    """Discard a draft: draft -> discarded."""
    raise NotImplementedError("A3: conversations.discard")


def unanswered(conn: sqlite3.Connection, channel: str) -> list[Row]:
    """Return incoming messages with no live reply yet."""
    raise NotImplementedError("A3: conversations.unanswered")


def pending_to_send(conn: sqlite3.Connection, channel: str) -> list[Row]:
    """Return approved outgoing messages + conversation external_id."""
    raise NotImplementedError("A3: conversations.pending_to_send")


def mark_sent(conn: sqlite3.Connection, message_id: int, now: datetime) -> None:
    """Mark an outgoing message as sent."""
    raise NotImplementedError("A3: conversations.mark_sent")


def mark_failed(conn: sqlite3.Connection, message_id: int, error: str) -> None:
    """Mark an outgoing message as failed, storing the error in note. Never resent automatically."""
    raise NotImplementedError("A3: conversations.mark_failed")
