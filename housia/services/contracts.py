"""Unit B5 — contracts: contract status and the signed contract.

Contract: DESIGN.md section 7 (contracts.py).

The contract can never be `signed` without a file.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3
    from datetime import datetime


def demo_contract_files() -> list[str]:
    """Return the fake signed contracts in static/demo/."""
    return []


def set_contract_status(conn: sqlite3.Connection, property_id: int, status: str,
                        now: datetime) -> None:
    """Set the contract status. status: 'pending' | 'sent'; needs a finalist."""
    raise NotImplementedError("B5: contracts.set_contract_status")


def attach_signed(conn: sqlite3.Connection, property_id: int, file_name: str,
                  now: datetime) -> None:
    """Attach the signed contract.

    - requires status 'sent'
    - sets 'signed' + signed_contract_file
    - finalist -> 'completed'
    - every other application of the property -> 'closed' with a polite notification
    """
    raise NotImplementedError("B5: contracts.attach_signed")
