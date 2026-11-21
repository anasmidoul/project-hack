"""Unit A4 — reply engine: write a reply to a portal message.

Contract: DESIGN.md section 7 (reply_engine.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass
class ReplyDecision:
    text: str
    needs_landlord: bool        # True = do not send without the landlord
    reason: str                 # why it was flagged, or ''


def generate_reply(prop: Mapping, history: list[Mapping], incoming: str,
                   contact_name: str, applicant_link: str) -> ReplyDecision:
    """Generate a reply to an incoming message.

    Rules:
    - Pure function: no database, no browser. `history` items have `direction` and `body`.
    - Two engines chosen by `config.REPLY_ENGINE`: `template` (no API key, keyword rules) and `llm`.
    - First message of a conversation: greet by name, give the key facts (rent, type, city), say
      which document is needed, and give `applicant_link` as the next step.
    - Later messages: answer only from `prop` columns and `prop['facts']`. If the answer is not
      there, set `needs_landlord=True` with a `reason` and a holding reply. Never invent facts.
    - Every reply ends with a line saying it was written by the landlord's assistant.
    - The `llm` engine falls back to `template` on any error.
    - The `llm` engine calls the model only through `llm.complete(system, user, known)`, passing
      the contact name in `known`. It never imports a model SDK.
    """
    raise NotImplementedError("A4: reply_engine.generate_reply")
