"""Unit B5 — postviewing: attendance and final candidate selection.

Contract: DESIGN.md section 7 (postviewing.py).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3
    from datetime import datetime

    Row = sqlite3.Row


def set_attendance(conn: sqlite3.Connection, slot_id: int, value: str, now: datetime) -> None:
    """Record attendance. value: 'attended' | 'absent'; the slot must be booked."""
    raise NotImplementedError("B5: postviewing.set_attendance")


def attended_applications(conn: sqlite3.Connection, property_id: int) -> list[Row]:
    """Return the applications of the property that attended a viewing."""
    raise NotImplementedError("B5: postviewing.attended_applications")


def select_finalist(conn: sqlite3.Connection, property_id: int, application_id: int,
                    now: datetime) -> None:
    """Select the final candidate. Must have attended; one per property."""
    raise NotImplementedError("B5: postviewing.select_finalist")
