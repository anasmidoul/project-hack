"""The interface every portal channel implements."""

import hashlib
from dataclasses import dataclass
from typing import Protocol


@dataclass
class IncomingMessage:
    external_conversation_id: str
    external_message_id: str  # stable id; if the portal shows none, use make_message_id()
    contact_name: str
    text: str
    received_at: str | None = None
    listing_ref: str | None = None


class ChannelError(Exception):
    """Reading or sending on a portal failed."""


class Channel(Protocol):
    name: str  # 'mock' | 'idealista' | 'badi'

    def fetch_new_messages(self) -> list[IncomingMessage]: ...

    def send_reply(self, external_conversation_id: str, text: str) -> None: ...  # raises ChannelError


def make_message_id(conversation_id: str, text: str, received_at: str | None) -> str:
    """Stable sha1 hex id for a message the portal gives no id for.

    Whitespace in the text is normalised, so small rendering differences give the same id.
    """
    normalised = " ".join((text or "").split())
    raw = "\x1f".join([str(conversation_id), normalised, received_at or ""])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()
