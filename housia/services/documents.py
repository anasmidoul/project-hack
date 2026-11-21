"""Unit B2 — documents: request, upload, approve and correct applicant documents.

Contract: DESIGN.md section 7 (documents.py).

Granting calendar access directly is `core.grant_calendar_access(..., invited_by='landlord', ...)`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3
    from datetime import datetime


def demo_files() -> list[str]:
    """Return the fake applicant documents in static/demo/."""
    return []


def request_document(conn: sqlite3.Connection, application_id: int, now: datetime) -> None:
    """Landlord requests the document: new -> docs_requested."""
    raise NotImplementedError("B2: documents.request_document")


def upload_document(conn: sqlite3.Connection, application_id: int, file_name: str,
                    now: datetime) -> None:
    """Applicant submits a file: docs_requested/docs_correction -> docs_uploaded.

    file_name must be in demo_files().
    """
    raise NotImplementedError("B2: documents.upload_document")


def approve_document(conn: sqlite3.Connection, application_id: int, now: datetime) -> None:
    """Landlord approves: docs_uploaded -> docs_approved."""
    raise NotImplementedError("B2: documents.approve_document")


def request_correction(conn: sqlite3.Connection, application_id: int, note: str,
                       now: datetime) -> None:
    """Landlord asks for a correction: docs_uploaded -> docs_correction, storing note in doc_note."""
    raise NotImplementedError("B2: documents.request_correction")
