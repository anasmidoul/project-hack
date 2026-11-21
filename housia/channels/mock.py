"""Unit A1 — mock channel: mock portal channel (reads and writes mock_threads / mock_messages).

Contract: DESIGN.md section 8 (Channels and worker).

Never import browser_use or openai at module top level.
"""
from __future__ import annotations

from housia import core, db
from housia.channels.base import ChannelError, IncomingMessage


class MockChannel:
    """Channel 'mock'. Takes no constructor arguments."""

    name = "mock"

    def __init__(self) -> None:
        pass

    def fetch_new_messages(self) -> list[IncomingMessage]:
        """Return candidate messages not handed over yet, oldest first, and mark them fetched."""
        with db.tx() as conn:
            rows = conn.execute(
                "SELECT m.id, m.thread_id, m.body, m.created_at, t.contact_name, t.listing_ref "
                "FROM mock_messages m JOIN mock_threads t ON t.id = m.thread_id "
                "WHERE m.sender = 'candidate' AND m.fetched = 0 "
                "ORDER BY m.created_at, m.id"
            ).fetchall()
            conn.executemany(
                "UPDATE mock_messages SET fetched = 1 WHERE id = ?", [(r["id"],) for r in rows]
            )
        return [
            IncomingMessage(
                external_conversation_id=str(r["thread_id"]),
                external_message_id=str(r["id"]),
                contact_name=r["contact_name"],
                text=r["body"],
                received_at=r["created_at"],
                listing_ref=r["listing_ref"],
            )
            for r in rows
        ]

    def send_reply(self, external_conversation_id: str, text: str) -> None:
        """Send text in the given conversation. Raises ChannelError on failure."""
        try:
            thread_id = int(external_conversation_id)
        except (TypeError, ValueError):
            raise ChannelError(f"Unknown mock thread: {external_conversation_id!r}")
        with db.tx() as conn:
            found = conn.execute(
                "SELECT 1 FROM mock_threads WHERE id = ?", (thread_id,)
            ).fetchone()
            if not found:
                raise ChannelError(f"Unknown mock thread: {external_conversation_id!r}")
            conn.execute(
                "INSERT INTO mock_messages (thread_id, sender, body, created_at) "
                "VALUES (?, 'landlord', ?, ?)",
                (thread_id, text, core.now(conn).replace(microsecond=0).isoformat()),
            )
