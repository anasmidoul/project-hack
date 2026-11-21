"""Unit B5 — postviewing: attendance and final candidate selection.

Contract: DESIGN.md section 7 (postviewing.py).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from housia import core

if TYPE_CHECKING:
    import sqlite3
    from datetime import datetime

    Row = sqlite3.Row


def set_attendance(conn: sqlite3.Connection, slot_id: int, value: str, now: datetime) -> None:
    """Record attendance. value: 'attended' | 'absent'; the slot must be booked."""
    if value not in {"attended", "absent"}:
        raise core.DomainError("Attendance must be attended or absent.")
    slot = conn.execute(
        "SELECT property_id, booked_application_id FROM slots WHERE id = ?", (slot_id,)
    ).fetchone()
    if slot is None:
        raise core.DomainError("Viewing slot not found.")
    if slot["booked_application_id"] is None:
        raise core.DomainError("Attendance can only be recorded for a booked viewing.")
    status = value
    conn.execute("UPDATE slots SET attendance = ? WHERE id = ?", (value, slot_id))
    core.set_status(conn, slot["booked_application_id"], status)


def attended_applications(conn: sqlite3.Connection, property_id: int) -> list[Row]:
    """Return the applications of the property that attended a viewing."""
    return conn.execute(
        "SELECT DISTINCT a.* FROM applications a JOIN slots s "
        "ON s.booked_application_id = a.id "
        "WHERE s.property_id = ? AND s.attendance = 'attended' "
        "ORDER BY a.created_at, a.id",
        (property_id,),
    ).fetchall()


def select_finalist(conn: sqlite3.Connection, property_id: int, application_id: int,
                    now: datetime) -> None:
    """Select the final candidate. Must have attended; one per property."""
    prop = conn.execute(
        "SELECT finalist_application_id, contract_status FROM properties WHERE id = ?",
        (property_id,),
    ).fetchone()
    if prop is None:
        raise core.DomainError("Property not found.")
    attended = conn.execute(
        "SELECT 1 FROM slots WHERE property_id = ? AND booked_application_id = ? "
        "AND attendance = 'attended' LIMIT 1",
        (property_id, application_id),
    ).fetchone()
    if attended is None:
        raise core.DomainError("Only an applicant who attended a viewing can be selected.")
    if prop["finalist_application_id"] is not None and prop["finalist_application_id"] != application_id:
        raise core.DomainError("A finalist has already been selected for this property.")
    if prop["contract_status"] == "signed":
        raise core.DomainError("The signed contract is already complete.")
    conn.execute("UPDATE properties SET finalist_application_id = ? WHERE id = ?", (application_id, property_id))
    core.set_status(conn, application_id, "finalist")
