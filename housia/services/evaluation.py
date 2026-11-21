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
    raise NotImplementedError("B3: evaluation.rank")


def evaluate(conn: sqlite3.Connection, property_id: int, now: datetime) -> EvaluationResult:
    """Run the evaluation.

    In assisted mode it changes nothing. In automatic mode it calls
    core.grant_calendar_access(..., invited_by='auto') for the top `remaining` proposals.
    """
    raise NotImplementedError("B3: evaluation.evaluate")


def invite(conn: sqlite3.Connection, property_id: int, application_ids: list[int],
           now: datetime) -> None:
    """Assisted confirmation: grant calendar access to the selected applications.

    Raises DomainError if the selection exceeds `remaining`.
    """
    raise NotImplementedError("B3: evaluation.invite")
