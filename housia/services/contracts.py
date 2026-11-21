"""Unit B5 — contracts: contract status and the signed contract.

Contract: DESIGN.md section 7 (contracts.py).

The contract can never be `signed` without a file.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from pathlib import Path

from housia import core

DEMO_DIR = Path(__file__).resolve().parents[1] / "static" / "demo"

if TYPE_CHECKING:
    import sqlite3
    from datetime import datetime


def demo_contract_files() -> list[str]:
    """Return the fake signed contracts in static/demo/."""
    return sorted(
        path.name for path in DEMO_DIR.glob("*.pdf")
        if "contract" in path.name.lower() and path.is_file()
    )


def set_contract_status(conn: sqlite3.Connection, property_id: int, status: str,
                        now: datetime) -> None:
    """Set the contract status. status: 'pending' | 'sent'; needs a finalist."""
    if status not in {"pending", "sent"}:
        raise core.DomainError("Contract status must be pending or sent.")
    prop = conn.execute(
        "SELECT finalist_application_id, contract_status FROM properties WHERE id = ?", (property_id,)
    ).fetchone()
    if prop is None:
        raise core.DomainError("Property not found.")
    if prop["finalist_application_id"] is None:
        raise core.DomainError("Select a finalist before preparing a contract.")
    if prop["contract_status"] == "signed":
        raise core.DomainError("A signed contract cannot be changed.")
    conn.execute("UPDATE properties SET contract_status = ? WHERE id = ?", (status, property_id))


def attach_signed(conn: sqlite3.Connection, property_id: int, file_name: str,
                  now: datetime) -> None:
    """Attach the signed contract.

    - requires status 'sent'
    - sets 'signed' + signed_contract_file
    - finalist -> 'completed'
    - every other application of the property -> 'closed' with a polite notification
    """
    prop = conn.execute(
        "SELECT finalist_application_id, contract_status FROM properties WHERE id = ?", (property_id,)
    ).fetchone()
    if prop is None:
        raise core.DomainError("Property not found.")
    if prop["finalist_application_id"] is None:
        raise core.DomainError("Select a finalist before attaching a signed contract.")
    if prop["contract_status"] != "sent":
        raise core.DomainError("The contract must be sent before it can be signed.")
    if file_name not in demo_contract_files():
        raise core.DomainError("Choose a bundled demo contract file.")
    finalist_id = prop["finalist_application_id"]
    conn.execute(
        "UPDATE properties SET contract_status = 'signed', signed_contract_file = ? WHERE id = ?",
        (file_name, property_id),
    )
    core.set_status(conn, finalist_id, "completed")
    others = conn.execute(
        "SELECT id FROM applications WHERE property_id = ? AND id != ? AND status != 'closed'",
        (property_id, finalist_id),
    ).fetchall()
    for row in others:
        core.set_status(conn, row["id"], "closed")
        core.notify(
            conn, property_id=property_id, application_id=row["id"],
            title="The property has been rented",
            body="Thank you for your interest. Another applicant was selected for this property.",
            now=now,
        )
