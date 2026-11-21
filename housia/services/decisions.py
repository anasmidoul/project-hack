"""Landlord decisions on an application: accept (invite to a viewing) or decline.

The route orchestrates, because services never import each other:
  1. `check` the rule and read the rows (short transaction),
  2. `write_message` with no transaction open (it may call the model),
  3. in one transaction: `accept` / `decline`, save the outgoing message, notify.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from housia import config, core, llm, privacy

if TYPE_CHECKING:
    from collections.abc import Mapping

ACCEPT_STATUSES = ("docs_uploaded", "docs_approved")
DECLINE_STATUSES = ("new", "docs_requested", "docs_uploaded", "docs_correction", "docs_approved")
SIGNATURE = "This message was written by the landlord's assistant."
MESSAGE_TITLE = "Message from the landlord"

_PLACEHOLDER = re.compile(r"\[[A-Z]+_\d+\]")

_SYSTEM = (
    "You write a short message in English from a landlord's assistant to a person who applied "
    "to rent a property. The user text gives the decision, the property title and city, the "
    "applicant's name and, for an acceptance, the applicant's personal link.\n"
    "Rules:\n"
    "- Write 2 to 4 short sentences, polite and friendly. Greet the applicant by name.\n"
    "- Keep every bracketed placeholder such as [NAME_1] exactly as it is.\n"
    "- For an acceptance: say they are invited to a viewing and that they can now choose a "
    "viewing time at their personal link. Copy the link exactly.\n"
    "- For a rejection: thank them for their interest and say the application will not go "
    "further. Do not give any reason. Do not include a link.\n"
    "- Never invent facts, dates or promises. Do not add a signature; it is added for you."
)


def _first_name(application: Mapping) -> str:
    parts = (application["name"] or "").split()
    return parts[0] if parts else "there"


def _template(kind: str, prop: Mapping, application: Mapping, link: str | None) -> str:
    name = _first_name(application)
    if kind == "accept":
        return (
            f"Hello {name},\n"
            f"Thank you for your application for \"{prop['title']}\" in {prop['city']}. "
            "I am happy to invite you to a viewing.\n"
            f"You can now choose a viewing time here: {link}\n"
            f"{SIGNATURE}"
        )
    return (
        f"Hello {name},\n"
        f"Thank you for your interest in \"{prop['title']}\" in {prop['city']}. "
        "I am sorry, but your application will not go further.\n"
        "I wish you the best of luck in your search.\n"
        f"{SIGNATURE}"
    )


def _llm(kind: str, prop: Mapping, application: Mapping, link: str | None) -> str:
    decision = ("accept: invite the applicant to a viewing" if kind == "accept"
                else "reject: the application will not go further")
    user = (
        f"Decision: {decision}\n"
        f"Property: {prop['title']}\n"
        f"City: {prop['city']}\n"
        f"Applicant name: {application['name']}\n"
    )
    if kind == "accept":
        user += f"Applicant link: {link}\n"
    answer = (llm.complete(_SYSTEM, user, known=privacy.known_values(application)) or "").strip()
    if not answer or _PLACEHOLDER.search(answer):
        raise ValueError("unusable model answer")
    if kind == "accept" and link not in answer:
        answer = f"{answer}\nYou can now choose a viewing time here: {link}"
    return f"{answer}\n{SIGNATURE}"


def write_message(kind: str, prop: Mapping, application: Mapping, link: str | None) -> str:
    """Text of the decision message. kind: 'accept' (needs `link`) or 'decline' (no link).

    May call the model: call it with no database transaction open.
    """
    if kind not in ("accept", "decline"):
        raise ValueError(f"unknown decision: {kind}")
    if config.REPLY_ENGINE == "llm":
        try:
            return _llm(kind, prop, application, link)
        except Exception:
            pass
    return _template(kind, prop, application, link)


def check(conn, application_id, kind: str):
    """Raise DomainError if the decision is not allowed now. Returns (application, property)."""
    application = conn.execute(
        "SELECT * FROM applications WHERE id = ?", (application_id,)
    ).fetchone()
    if application is None:
        raise core.DomainError("Application not found.")
    prop = conn.execute(
        "SELECT * FROM properties WHERE id = ?", (application["property_id"],)
    ).fetchone()
    if prop is None:
        raise core.DomainError("Property not found.")
    if kind == "accept":
        if application["status"] not in ACCEPT_STATUSES:
            raise core.DomainError(
                "An applicant can be accepted only after the document has been uploaded or approved."
            )
        if core.invited_count(conn, prop["id"]) >= prop["invite_limit"]:
            raise core.DomainError(
                f"The invite limit of {prop['invite_limit']} for this property has been reached."
            )
    elif kind == "decline":
        if application["status"] not in DECLINE_STATUSES:
            raise core.DomainError("This application can no longer be declined.")
    else:
        raise core.DomainError(f"Unknown decision: {kind}.")
    return application, prop


def accept(conn, application_id, now) -> None:
    """Invite to a viewing: calendar access, status 'invited' (core enforces the invite limit)."""
    check(conn, application_id, "accept")
    core.grant_calendar_access(conn, application_id, "landlord", now)


def decline(conn, application_id, now) -> None:
    """Close the application."""
    check(conn, application_id, "decline")
    core.set_status(conn, application_id, "closed")
