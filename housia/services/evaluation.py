"""Unit B3 — evaluation: rank applicants and invite them to the calendar.

Contract: DESIGN.md section 7 (evaluation.py).

Rules:
- Eligible: `status = 'docs_approved'`.
- Score: number of future slots of the property with no booking and no offer whose
  `core.time_band(starts_at)` is in the applicant's `availability`. Higher first.
- Tie-break: earlier `created_at`.
- `evaluate` in assisted mode changes nothing. In automatic mode it calls
  `core.grant_calendar_access(..., invited_by='auto')` for the top `remaining` proposals.
- `invite` raises `DomainError` if the selection exceeds `remaining`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from housia import core

if TYPE_CHECKING:
    import sqlite3
    from datetime import datetime


@dataclass
class Proposal:
    application_id: int
    name: str
    position: int
    score: int
    total_slots: int
    explanation: str      # "Can attend 3 of 4 open slots. Applied 2nd."


@dataclass
class EvaluationResult:
    mode: str                        # 'assisted' | 'automatic'
    proposals: list[Proposal]        # ranked, best first
    remaining: int                   # invite_limit - invited_count, before this run
    invited_ids: list[int]           # automatic: who was invited now; assisted: []
    left_out_ids: list[int]          # automatic: eligible but over the limit


def rank(conn: sqlite3.Connection, property_id: int, now: datetime) -> list[Proposal]:
    """Rank eligible applications (status 'docs_approved'), best first.

    Score = number of future slots of the property with no booking and no offer whose
    core.time_band(starts_at) is in the applicant's availability. Higher first.
    Tie-break: earlier created_at.
    """
    prop = conn.execute("SELECT id FROM properties WHERE id = ?", (property_id,)).fetchone()
    if prop is None:
        raise core.DomainError("Property not found.")
    candidates = conn.execute(
        "SELECT id, name, availability, created_at FROM applications "
        "WHERE property_id = ? AND status = 'docs_approved' ORDER BY created_at, id",
        (property_id,),
    ).fetchall()
    application_order = {
        row["id"]: index for index, row in enumerate(conn.execute(
            "SELECT id FROM applications WHERE property_id=? ORDER BY created_at,id", (property_id,)
        ).fetchall(), 1)
    }
    slots = conn.execute(
        "SELECT starts_at FROM slots WHERE property_id = ? AND starts_at > ? "
        "AND booked_application_id IS NULL AND offer_application_id IS NULL ORDER BY starts_at",
        (property_id, now.replace(microsecond=0).isoformat()),
    ).fetchall()
    bands = [core.time_band(slot["starts_at"]) for slot in slots]
    proposals = []
    for row in candidates:
        availability = {value.strip() for value in (row["availability"] or "").split(",") if value.strip()}
        score = sum(band in availability for band in bands)
        proposals.append((row, score))
    proposals.sort(key=lambda item: (-item[1], item[0]["created_at"], item[0]["id"]))
    total = len(slots)
    result = []
    for position, (row, score) in enumerate(proposals, 1):
        applied = application_order[row["id"]]
        applied_ordinal = "th" if 10 <= applied % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(applied % 10, "th")
        result.append(Proposal(
            application_id=row["id"], name=row["name"], position=position,
            score=score, total_slots=total,
            explanation=f"Can attend {score} of {total} open slots. Applied {applied}{applied_ordinal}.",
        ))
    return result


def evaluate(conn: sqlite3.Connection, property_id: int, now: datetime) -> EvaluationResult:
    """Run the evaluation.

    In assisted mode it changes nothing. In automatic mode it calls
    core.grant_calendar_access(..., invited_by='auto') for the top `remaining` proposals.
    """
    prop = conn.execute("SELECT eval_mode, invite_limit FROM properties WHERE id = ?", (property_id,)).fetchone()
    if prop is None:
        raise core.DomainError("Property not found.")
    proposals = rank(conn, property_id, now)
    remaining = max(0, prop["invite_limit"] - core.invited_count(conn, property_id))
    invited_ids = []
    left_out_ids = []
    if prop["eval_mode"] == "automatic":
        eligible = [proposal.application_id for proposal in proposals]
        invited_ids = eligible[:remaining]
        left_out_ids = eligible[remaining:]
        for application_id in invited_ids:
            core.grant_calendar_access(conn, application_id, "auto", now)
    return EvaluationResult(prop["eval_mode"], proposals, remaining, invited_ids, left_out_ids)


def invite(conn: sqlite3.Connection, property_id: int, application_ids: list[int],
           now: datetime) -> None:
    """Assisted confirmation: grant calendar access to the selected applications.

    Raises DomainError if the selection exceeds `remaining`.
    """
    prop = conn.execute("SELECT eval_mode FROM properties WHERE id = ?", (property_id,)).fetchone()
    if prop is None:
        raise core.DomainError("Property not found.")
    if prop["eval_mode"] != "assisted":
        raise core.DomainError("Manual invitations are only available in assisted mode.")
    if len(set(application_ids)) != len(application_ids):
        raise core.DomainError("An applicant can only be selected once.")
    ranked_ids = {proposal.application_id for proposal in rank(conn, property_id, now)}
    if any(application_id not in ranked_ids for application_id in application_ids):
        raise core.DomainError("Only eligible applicants for this property can be invited.")
    remaining = max(0, conn.execute(
        "SELECT invite_limit FROM properties WHERE id = ?", (property_id,)
    ).fetchone()[0] - core.invited_count(conn, property_id))
    if len(application_ids) > remaining:
        raise core.DomainError(f"Only {remaining} invitation(s) remain for this property.")
    for application_id in application_ids:
        core.grant_calendar_access(conn, application_id, "landlord", now)
