"""Unit B7 — seed data: demo content loaded by db.reset_db().

Contract: DESIGN.md section 10.

seed.run(conn, now) must make both demo moments work straight after a reset. Dates are
relative to `now`.

- Property 1: residential, Madrid, eval_mode='assisted', reply_mode='automatic',
  invite_limit=3, with facts filled in. Six applications: one new, one docs_requested,
  one docs_uploaded, three docs_approved with different availability, two of them tied on
  score so the tie-break shows. Three free slots.
- Property 2: temporary, Valencia, eval_mode='automatic', reply_mode='assisted',
  invite_limit=5. Three applicants already invited: X has a slot tomorrow, Y then Z are on
  its waiting list. Four more docs_approved, so an automatic run invites two and leaves two.
- Mock portal: three unanswered threads for property 1: a first contact, a question the
  facts answer, and a question they do not.
- Names are fictional, emails end in @example.com, phones look like 600 000 001.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3
    from datetime import datetime


def run(conn: sqlite3.Connection, now: datetime) -> None:
    """Insert the demo data. Harmless stub: does nothing until B7 implements it."""
    return None
