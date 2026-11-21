"""Unit A4 — reply engine: write a reply to a portal message.

Contract: DESIGN.md section 7 (reply_engine.py).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from housia import config, llm

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass
class ReplyDecision:
    text: str
    needs_landlord: bool        # True = do not send without the landlord
    reason: str                 # why it was flagged, or ''


SIGNATURE = "This message was written by the landlord's assistant."
HOLDING = "I will check with the landlord and get back to you."
_TYPES = {"residential": "long-term rental", "temporary": "temporary rental"}

# topic -> (words in the incoming message, words to look for in `facts`)
# Topics answered from columns have no facts words.
_TOPICS: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
    ("price", ("price", "rent", "cost", "how much", "eur", "euro", "precio", "alquiler"), ()),
    ("address", ("address", "location", "where", "located", "street", "neighbourhood",
                 "neighborhood", "direccion", "dirección"), ()),
    ("pets", ("pet", "dog", "cat", "animal", "mascota"), ("pet", "dog", "cat", "animal")),
    ("furnished", ("furnish", "unfurnished", "amueblado"), ("furnish",)),
    ("deposit", ("deposit", "fianza", "bond"), ("deposit", "fianza")),
    ("available", ("available from", "availability", "move in", "move-in", "start date",
                   "when can i", "from when", "disponible"), ("available", "move-in", "move in")),
    ("stay", ("how long", "minimum stay", "min stay", "minimum", "duration", "length of",
              "long can", "months"), ("minimum", "stay", "month", "duration", "lease")),
    ("viewing", ("viewing", "visit", "see the", "see it", "show the", "tour"), ()),
    ("documents", ("document", "paperwork", "payslip", "papers", "documentation"), ()),
]


def _has(text: str, words: tuple[str, ...]) -> bool:
    return any(w in text for w in words)


def _quote(facts: str, words: tuple[str, ...]) -> str | None:
    """Return the first line or sentence of `facts` that mentions one of `words`."""
    for line in (facts or "").splitlines():
        for part in re.split(r"(?<=[.!?;])\s+", line):
            if part.strip() and _has(part.lower(), words):
                return part.strip()
    return None


def _first_contact(history: list[Mapping]) -> bool:
    return not any(m.get("direction") == "out" for m in history or [])


def _template(prop: Mapping, history: list[Mapping], incoming: str,
              contact_name: str, applicant_link: str) -> ReplyDecision:
    if _first_contact(history):
        kind = _TYPES.get(prop["rental_type"], prop["rental_type"])
        text = (
            f"Hello {contact_name},\n"
            f"Thank you for your interest in \"{prop['title']}\". It is a {kind} in "
            f"{prop['city']}, rent {prop['rent_eur']} EUR per month.\n"
            f"To continue, please send this document: {prop['required_document']}.\n"
            f"You can do it here: {applicant_link}\n"
            f"{SIGNATURE}"
        )
        return ReplyDecision(text, False, "")

    msg = (incoming or "").lower()
    answers: list[str] = []
    missing: list[str] = []
    for topic, ask_words, fact_words in _TOPICS:
        if not _has(msg, ask_words):
            continue
        if topic == "price":
            answers.append(f"The rent is {prop['rent_eur']} EUR per month.")
        elif topic == "address":
            answers.append(f"The address is {prop['address']}, {prop['city']}.")
        elif topic == "viewing":
            answers.append(f"You can ask for a viewing here: {applicant_link}")
        elif topic == "documents":
            answers.append(f"The document we need is: {prop['required_document']}. "
                           f"You can send it here: {applicant_link}")
        else:
            quote = _quote(prop.get("facts", ""), fact_words)
            if quote:
                answers.append(f"From the listing: \"{quote}\"")
            else:
                missing.append(topic)

    if not answers and not missing:
        missing.append("unrecognised question")
    if missing:
        parts = [f"Hello {contact_name},", *answers, HOLDING, SIGNATURE]
        return ReplyDecision("\n".join(parts), True,
                             "No answer in the listing data for: " + ", ".join(missing))
    return ReplyDecision("\n".join([f"Hello {contact_name},", *answers, SIGNATURE]), False, "")


_SYSTEM = (
    "You write short, polite replies in English from a landlord's assistant to a person who "
    "asked about a rental listing on a portal.\n"
    "Rules:\n"
    "- Answer only from the listing data given in the user text. Never invent facts, prices, "
    "dates or promises.\n"
    "- If the answer is not in the listing data, reply with the single word UNKNOWN and nothing "
    "else.\n"
    "- For the first message of a conversation: greet the person by name, give the rent, the "
    "rental type and the city, say which document is needed, and give the applicant link as the "
    "next step.\n"
    "- For a viewing request, point to the applicant link.\n"
    "- Rental type 'residential' means long-term rental; 'temporary' means temporary rental.\n"
    "- Keep it short. Do not add a signature; it is added for you."
)


def _llm(prop: Mapping, history: list[Mapping], incoming: str,
         contact_name: str, applicant_link: str) -> ReplyDecision:
    kind = _TYPES.get(prop["rental_type"], prop["rental_type"])
    convo = "\n".join(
        f"{'Landlord' if m.get('direction') == 'out' else 'Candidate'}: {m.get('body', '')}"
        for m in history or []
    ) or "(no earlier messages; this is the first contact)"
    user = (
        "Listing data:\n"
        f"Title: {prop['title']}\nAddress: {prop['address']}\nCity: {prop['city']}\n"
        f"Rental type: {kind}\nRent: {prop['rent_eur']} EUR per month\n"
        f"Description: {prop.get('description', '')}\n"
        f"Facts: {prop.get('facts', '')}\n"
        f"Required document: {prop['required_document']}\n"
        f"Applicant link: {applicant_link}\n\n"
        f"Candidate name: {contact_name}\n\n"
        f"Conversation so far:\n{convo}\n\n"
        f"New message from the candidate:\n{incoming}\n"
    )
    answer = (llm.complete(_SYSTEM, user, known={"NAME": contact_name}) or "").strip()
    if not answer:
        raise ValueError("empty model answer")
    if "UNKNOWN" in answer:
        text = f"Hello {contact_name},\n{HOLDING}\n{SIGNATURE}"
        return ReplyDecision(text, True, "The model could not answer from the listing data")
    return ReplyDecision(f"{answer}\n{SIGNATURE}", False, "")


def generate_reply(prop: Mapping, history: list[Mapping], incoming: str,
                   contact_name: str, applicant_link: str) -> ReplyDecision:
    """Generate a reply to an incoming message (DESIGN.md section 7, reply_engine.py)."""
    prop = dict(prop)  # also accepts sqlite3.Row, which has no .get
    if config.REPLY_ENGINE == "llm":
        try:
            return _llm(prop, history, incoming, contact_name, applicant_link)
        except Exception:
            pass
    return _template(prop, history, incoming, contact_name, applicant_link)
