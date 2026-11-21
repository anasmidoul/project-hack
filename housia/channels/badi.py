"""Unit A6 — badi channel: Badi channel driven by browser-use (same approach as A2, built last).

Contract: DESIGN.md section 8 (Channels and worker).

Never import browser_use or openai at module top level.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from housia.channels.base import IncomingMessage


class BadiChannel:
    """Channel 'badi'. Takes no constructor arguments."""

    name = "badi"

    def __init__(self) -> None:
        pass

    def fetch_new_messages(self) -> list[IncomingMessage]:
        """Return new incoming messages. May return a message twice; dedup is done by
        conversations.record_incoming."""
        raise NotImplementedError("A6: badi.BadiChannel.fetch_new_messages")

    def send_reply(self, external_conversation_id: str, text: str) -> None:
        """Send text in the given conversation. Raises ChannelError on failure."""
        raise NotImplementedError("A6: badi.BadiChannel.send_reply")
