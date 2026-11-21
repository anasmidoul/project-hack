"""Unit B2 — applications: create and read applications.

Contract: DESIGN.md section 7 (applications.py).
"""
from __future__ import annotations

from typing import TYPE_CHECKING
import secrets

from housia import core

if TYPE_CHECKING:
    import sqlite3
    from datetime import datetime

    Row = sqlite3.Row


def create_application(conn: sqlite3.Connection, property_id: int, data: dict,
                       source: str, now: datetime) -> int:
    """Create an application and return its id.

    - data keys: name (required), email, phone, preferences, availability (list[str])
    - generates token; notifies the landlord
    """
    from housia.services import properties

    properties.get_property(conn, property_id)
    if source not in {"link", "idealista", "badi", "mock", "fotocasa", "whatsapp", "phone"}:
        raise core.DomainError("Unknown application source.")
    values = _details(data)
    token = secrets.token_urlsafe(24)
    cursor = conn.execute(
        "INSERT INTO applications (property_id,token,name,email,phone,source,preferences,availability,created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (property_id, token, values["name"], values["email"], values["phone"], source,
         values["preferences"], ",".join(values["availability"]), now.replace(microsecond=0).isoformat()),
    )
    core.notify(conn, property_id=property_id, application_id=None,
                title="New rental application", body=f"{values['name']} applied for a property.", now=now)
    return cursor.lastrowid


def update_details(conn: sqlite3.Connection, application_id: int, data: dict) -> None:
    """Update details. Same keys as create_application; used when a portal contact completes their details."""
    get_application(conn, application_id)
    values = _details(data)
    conn.execute(
        "UPDATE applications SET name=?,email=?,phone=?,preferences=?,availability=? WHERE id=?",
        (values["name"], values["email"], values["phone"], values["preferences"],
         ",".join(values["availability"]), application_id),
    )


def _details(data: dict) -> dict:
    name = str(data.get("name", "")).strip()
    if not name:
        raise core.DomainError("Name is required.")
    available = data.get("availability", [])
    if isinstance(available, str):
        available = available.split(",")
    availability = list(dict.fromkeys(str(value).strip() for value in available if str(value).strip()))
    if any(value not in core.TIME_BANDS for value in availability):
        raise core.DomainError("Choose valid availability options.")
    return {
        "name": name,
        "email": str(data.get("email", "")).strip(),
        "phone": str(data.get("phone", "")).strip(),
        "preferences": str(data.get("preferences", "")).strip(),
        "availability": availability,
    }


def get_application(conn: sqlite3.Connection, application_id: int) -> Row:
    """Return one application. A missing id raises DomainError."""
    row = conn.execute("SELECT * FROM applications WHERE id = ?", (application_id,)).fetchone()
    if row is None:
        raise core.DomainError("Application not found.")
    return row


def get_by_token(conn: sqlite3.Connection, token: str) -> Row:
    """Return the application with this token. A missing token raises DomainError."""
    row = conn.execute("SELECT * FROM applications WHERE token = ?", (token,)).fetchone()
    if row is None:
        raise core.DomainError("Application not found.")
    return row


def list_for_property(conn: sqlite3.Connection, property_id: int) -> list[Row]:
    """Return the applications of a property, ordered by created_at."""
    from housia.services import properties

    properties.get_property(conn, property_id)
    return conn.execute(
        "SELECT * FROM applications WHERE property_id = ? ORDER BY created_at, id", (property_id,)
    ).fetchall()
