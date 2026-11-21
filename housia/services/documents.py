"""Unit B2 — documents: request, upload, approve and correct applicant documents.

Contract: DESIGN.md section 7 (documents.py).

Granting calendar access directly is `core.grant_calendar_access(..., invited_by='landlord', ...)`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from pathlib import Path

from housia import core

DEMO_DIR = Path(__file__).resolve().parents[1] / "static" / "demo"

if TYPE_CHECKING:
    import sqlite3
    from datetime import datetime


def demo_files() -> list[str]:
    """Return the fake applicant documents in static/demo/."""
    return sorted(path.name for path in DEMO_DIR.glob("*.pdf")
                  if "contract" not in path.name.lower() and path.is_file())


def request_document(conn: sqlite3.Connection, application_id: int, now: datetime) -> None:
    """Landlord requests the document: new -> docs_requested."""
    from housia.services.applications import get_application

    app = get_application(conn, application_id)
    if app["status"] != "new":
        raise core.DomainError("A document can only be requested from a new applicant.")
    core.set_status(conn, application_id, "docs_requested")
    core.notify(conn, property_id=app["property_id"], application_id=application_id,
                title="Document requested", body="Please submit the requested document.", now=now)


def upload_document(conn: sqlite3.Connection, application_id: int, file_name: str,
                    now: datetime) -> None:
    """Applicant submits a file: docs_requested/docs_correction -> docs_uploaded.

    file_name must be in demo_files().
    """
    if file_name not in demo_files():
        raise core.DomainError("Choose one of the bundled demo documents.")
    from housia.services.applications import get_application

    app = get_application(conn, application_id)
    if app["status"] not in {"docs_requested", "docs_correction"}:
        raise core.DomainError("A document has not been requested for this applicant.")
    conn.execute("UPDATE applications SET doc_file=?,doc_note=NULL WHERE id=?", (file_name, application_id))
    core.set_status(conn, application_id, "docs_uploaded")
    core.notify(conn, property_id=app["property_id"], application_id=None,
                title="Document received", body=f"{app['name']} submitted {file_name}.", now=now)


def approve_document(conn: sqlite3.Connection, application_id: int, now: datetime) -> None:
    """Landlord approves: docs_uploaded -> docs_approved."""
    from housia.services.applications import get_application

    app = get_application(conn, application_id)
    if app["status"] != "docs_uploaded":
        raise core.DomainError("Only an uploaded document can be approved.")
    core.set_status(conn, application_id, "docs_approved")
    core.notify(conn, property_id=app["property_id"], application_id=application_id,
                title="Document approved", body="Your document was approved.", now=now)


def request_correction(conn: sqlite3.Connection, application_id: int, note: str,
                       now: datetime) -> None:
    """Landlord asks for a correction: docs_uploaded -> docs_correction, storing note in doc_note."""
    note = str(note or "").strip()
    if not note:
        raise core.DomainError("A correction note is required.")
    from housia.services.applications import get_application

    app = get_application(conn, application_id)
    if app["status"] != "docs_uploaded":
        raise core.DomainError("A correction can only be requested for an uploaded document.")
    conn.execute("UPDATE applications SET doc_note=? WHERE id=?", (note, application_id))
    core.set_status(conn, application_id, "docs_correction")
    core.notify(conn, property_id=app["property_id"], application_id=application_id,
                title="Document correction requested", body=note, now=now)
