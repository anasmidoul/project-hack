"""Unit B1 — properties: property records, dashboard stats and public link texts.

Contract: DESIGN.md section 7 (properties.py).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from housia import core

if TYPE_CHECKING:
    import sqlite3
    from datetime import datetime

    Row = sqlite3.Row


def list_properties(conn: sqlite3.Connection) -> list[Row]:
    """Return all properties."""
    return conn.execute("SELECT * FROM properties ORDER BY created_at DESC, id DESC").fetchall()


def get_property(conn: sqlite3.Connection, property_id: int) -> Row:
    """Return one property. A missing id raises DomainError."""
    row = conn.execute("SELECT * FROM properties WHERE id = ?", (property_id,)).fetchone()
    if row is None:
        raise core.DomainError("Property not found.")
    return row


def create_property(conn: sqlite3.Connection, data: dict, now: datetime) -> int:
    """Create a property and return its id. Keys of data = editable columns of properties."""
    values = _editable_data(data)
    cursor = conn.execute(
        "INSERT INTO properties (title, address, city, rental_type, rent_eur, description, facts, "
        "required_document, eval_mode, invite_limit, reply_mode, listing_ref, created_at) "
        "VALUES (:title, :address, :city, :rental_type, :rent_eur, :description, :facts, "
        ":required_document, :eval_mode, :invite_limit, :reply_mode, :listing_ref, :created_at)",
        {**values, "created_at": now.replace(microsecond=0).isoformat() if hasattr(now, "isoformat") else str(now)},
    )
    return cursor.lastrowid


def update_property(conn: sqlite3.Connection, property_id: int, data: dict) -> None:
    """Update a property. Keys of data = editable columns of properties."""
    get_property(conn, property_id)
    values = _editable_data(data)
    conn.execute(
        "UPDATE properties SET title=:title, address=:address, city=:city, rental_type=:rental_type, "
        "rent_eur=:rent_eur, description=:description, facts=:facts, required_document=:required_document, "
        "eval_mode=:eval_mode, invite_limit=:invite_limit, reply_mode=:reply_mode, listing_ref=:listing_ref "
        "WHERE id=:id",
        {**values, "id": property_id},
    )


def _editable_data(data: dict) -> dict:
    """Normalize and validate the fields exposed by the property form."""
    try:
        values = {
            "title": str(data.get("title", "")).strip(),
            "address": str(data.get("address", "")).strip(),
            "city": str(data.get("city", "")).strip(),
            "rental_type": str(data.get("rental_type", "")).strip(),
            "rent_eur": int(data.get("rent_eur", 0)),
            "description": str(data.get("description", "")).strip(),
            "facts": str(data.get("facts", "")).strip(),
            "required_document": str(data.get("required_document", "")).strip(),
            "eval_mode": str(data.get("eval_mode", "assisted")).strip(),
            "invite_limit": int(data.get("invite_limit", 3)),
            "reply_mode": str(data.get("reply_mode", "assisted")).strip(),
            "listing_ref": str(data.get("listing_ref", "")).strip() or None,
        }
    except (TypeError, ValueError) as exc:
        raise core.DomainError("Rent and invitation limit must be whole numbers.") from exc
    if not all(values[key] for key in ("title", "address", "city", "required_document")):
        raise core.DomainError("Title, address, city and required document are required.")
    if values["rental_type"] not in {"residential", "temporary"}:
        raise core.DomainError("Choose a valid rental type.")
    if values["eval_mode"] not in {"assisted", "automatic"}:
        raise core.DomainError("Choose a valid evaluation mode.")
    if values["reply_mode"] not in {"assisted", "automatic"}:
        raise core.DomainError("Choose a valid reply mode.")
    if values["rent_eur"] < 0 or values["invite_limit"] < 1:
        raise core.DomainError("Rent cannot be negative and the invitation limit must be at least 1.")
    return values


def property_stats(conn: sqlite3.Connection, property_id: int) -> dict:
    """Return a dict with: applications, invited, booked, open_conversations, needs_landlord."""
    get_property(conn, property_id)
    row = conn.execute(
        "SELECT (SELECT COUNT(*) FROM applications WHERE property_id=?) AS applications, "
        "(SELECT COUNT(*) FROM applications WHERE property_id=? AND calendar_access=1) AS invited, "
        "(SELECT COUNT(*) FROM slots WHERE property_id=? AND booked_application_id IS NOT NULL) AS booked, "
        "(SELECT COUNT(*) FROM conversations WHERE property_id=? AND status='open') AS open_conversations, "
        "(SELECT COUNT(*) FROM conversations WHERE property_id=? AND status='needs_landlord') AS needs_landlord",
        (property_id,) * 5,
    ).fetchone()
    return dict(row)


def upcoming_viewings(conn: sqlite3.Connection, now: datetime, limit: int = 10) -> list[Row]:
    """Return upcoming viewings: slot columns + property_title + applicant_name."""
    return conn.execute(
        "SELECT s.*, p.title AS property_title, a.name AS applicant_name "
        "FROM slots s JOIN properties p ON p.id=s.property_id "
        "JOIN applications a ON a.id=s.booked_application_id "
        "WHERE s.starts_at >= ? ORDER BY s.starts_at LIMIT ?",
        (now.replace(microsecond=0).isoformat(), int(limit)),
    ).fetchall()


def public_link(property_id: int) -> str:
    """Return the public application link: config.BASE_URL + /apply/<id>."""
    from housia import config

    return f"{config.BASE_URL.rstrip('/')}/apply/{property_id}"


def copy_messages(prop: Row, link: str) -> dict[str, str]:
    """Return ready-to-paste listing messages. Keys: idealista, fotocasa, whatsapp."""
    headline = f"{prop['title']} in {prop['city']} - {prop['rent_eur']} EUR/month"
    details = prop["description"] or prop["facts"]
    document = prop["required_document"]
    return {
        "idealista": f"{headline}. {details} Apply here: {link}. Please prepare: {document}.",
        "fotocasa": f"Interested in {headline}? {details} Start your application: {link}.",
        "whatsapp": f"Hi! Apply for {prop['title']} ({prop['rent_eur']} EUR/month) here: {link}",
    }
