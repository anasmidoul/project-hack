"""Unit A2 — idealista channel: Idealista channel driven by browser-use.

Contract: DESIGN.md section 8 (Channels and worker).

Rules (DESIGN.md section 8, A2): send_reply types the text exactly and sends it once; if it
cannot confirm, raise ChannelError, never retry. Candidate text is untrusted data, never
instructions for the browser agent. When the inbox URL is not localhost, send only if the
contact name or id is in config.SEND_ALLOWLIST, else raise
ChannelError("contact not on the send allowlist"). Import browser_use lazily, inside methods.
Never import browser_use or openai at module top level.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from housia.channels.base import IncomingMessage


class IdealistaChannel:
    """Channel 'idealista'. Takes no constructor arguments."""

    name = "idealista"

    def __init__(self) -> None:
        pass

    def fetch_new_messages(self) -> list[IncomingMessage]:
        """Return new incoming messages. May return a message twice; dedup is done by
        conversations.record_incoming."""
        raise NotImplementedError("A2: idealista.IdealistaChannel.fetch_new_messages")

    def send_reply(self, external_conversation_id: str, text: str) -> None:
        """Send text in the given conversation. Raises ChannelError on failure."""
        raise NotImplementedError("A2: idealista.IdealistaChannel.send_reply")
