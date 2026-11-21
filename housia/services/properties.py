"""Unit B1 — properties: property records, dashboard stats and public link texts.

Contract: DESIGN.md section 7 (properties.py).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3
    from datetime import datetime

    Row = sqlite3.Row


def list_properties(conn: sqlite3.Connection) -> list[Row]:
    """Return all properties."""
    raise NotImplementedError("B1: properties.list_properties")


def get_property(conn: sqlite3.Connection, property_id: int) -> Row:
    """Return one property. A missing id raises DomainError."""
    raise NotImplementedError("B1: properties.get_property")


def create_property(conn: sqlite3.Connection, data: dict, now: datetime) -> int:
    """Create a property and return its id. Keys of data = editable columns of properties."""
    raise NotImplementedError("B1: properties.create_property")


def update_property(conn: sqlite3.Connection, property_id: int, data: dict) -> None:
    """Update a property. Keys of data = editable columns of properties."""
    raise NotImplementedError("B1: properties.update_property")


def property_stats(conn: sqlite3.Connection, property_id: int) -> dict:
    """Return a dict with: applications, invited, booked, open_conversations, needs_landlord."""
    raise NotImplementedError("B1: properties.property_stats")


def upcoming_viewings(conn: sqlite3.Connection, now: datetime, limit: int = 10) -> list[Row]:
    """Return upcoming viewings: slot columns + property_title + applicant_name."""
    raise NotImplementedError("B1: properties.upcoming_viewings")


def public_link(property_id: int) -> str:
    """Return the public application link: config.BASE_URL + /apply/<id>."""
    raise NotImplementedError("B1: properties.public_link")


def copy_messages(prop: Row, link: str) -> dict[str, str]:
    """Return ready-to-paste listing messages. Keys: idealista, fotocasa, whatsapp."""
    raise NotImplementedError("B1: properties.copy_messages")
