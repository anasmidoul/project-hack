"""Unit A1 — mock channel: mock portal channel (reads and writes mock_threads / mock_messages).

Contract: DESIGN.md section 8 (Channels and worker).

Never import browser_use or openai at module top level.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from housia.channels.base import IncomingMessage


class MockChannel:
    """Channel 'mock'. Takes no constructor arguments."""

    name = "mock"

    def __init__(self) -> None:
        pass

    def fetch_new_messages(self) -> list[IncomingMessage]:
        """Return new incoming messages. May return a message twice; dedup is done by
        conversations.record_incoming."""
        raise NotImplementedError("A1: mock.MockChannel.fetch_new_messages")

    def send_reply(self, external_conversation_id: str, text: str) -> None:
        """Send text in the given conversation. Raises ChannelError on failure."""
        raise NotImplementedError("A1: mock.MockChannel.send_reply")
