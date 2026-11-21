"""Unit B2 — applications: create and read applications.

Contract: DESIGN.md section 7 (applications.py).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

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
    raise NotImplementedError("B2: applications.create_application")


def update_details(conn: sqlite3.Connection, application_id: int, data: dict) -> None:
    """Update details. Same keys as create_application; used when a portal contact completes their details."""
    raise NotImplementedError("B2: applications.update_details")


def get_application(conn: sqlite3.Connection, application_id: int) -> Row:
    """Return one application. A missing id raises DomainError."""
    raise NotImplementedError("B2: applications.get_application")


def get_by_token(conn: sqlite3.Connection, token: str) -> Row:
    """Return the application with this token. A missing token raises DomainError."""
    raise NotImplementedError("B2: applications.get_by_token")


def list_for_property(conn: sqlite3.Connection, property_id: int) -> list[Row]:
    """Return the applications of a property, ordered by created_at."""
    raise NotImplementedError("B2: applications.list_for_property")
