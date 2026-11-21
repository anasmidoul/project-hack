"""Unit B6 tests: applicant routes (DESIGN.md section 9, Applicant pages)."""
from datetime import datetime, timedelta

import pytest

from housia import db


def _setup(status="new", name="Ana Lopez", token="tok1", access=0, email="", phone="", prop=True):
    """Insert a property (once) and an application. Returns the application id."""
    now = datetime.now().replace(microsecond=0).isoformat()
    with db.tx() as conn:
        if prop and not conn.execute("SELECT 1 FROM properties WHERE id=1").fetchone():
            conn.execute(
                "INSERT INTO properties (id, title, address, city, rental_type, rent_eur, "
                "required_document, invite_limit, created_at) VALUES "
                "(1, 'Flat', 'Calle 1', 'Madrid', 'residential', 900, 'Payslip', 5, ?)", (now,))
        return conn.execute(
            "INSERT INTO applications (property_id, token, name, email, phone, source, status, "
            "calendar_access, created_at) VALUES (1, ?, ?, ?, ?, 'mock', ?, ?, ?)",
            (token, name, email, phone, status, access, now)).lastrowid


def _one(sql, *args):
    with db.tx() as conn:
        return conn.execute(sql, args).fetchone()


def _slot():
    start = (datetime.now() + timedelta(days=2)).replace(microsecond=0).isoformat()
    with db.tx() as conn:
        return conn.execute("INSERT INTO slots (property_id, starts_at) VALUES (1, ?)", (start,)).lastrowid


def test_public_form_creates_application(client):
    _setup(token="other")
    assert client.get("/apply/1").status_code == 200
    r = client.post("/apply/1", data={
        "name": "Bea Ruiz", "email": "b@x.es", "phone": "600", "preferences": "quiet",
        "availability": ["morning", "weekend"]})
    row = _one("SELECT * FROM applications WHERE name='Bea Ruiz'")
    assert row["source"] == "link" and row["availability"] == "morning,weekend"
    assert (row["email"], row["phone"], row["preferences"]) == ("b@x.es", "600", "quiet")
    assert r.status_code == 302 and r.headers["Location"].endswith(f"/a/{row['token']}")


def test_applicant_page_and_unknown_token(client):
    _setup()
    assert client.get("/a/tok1").status_code == 200
    status = client.get("/a/nope").status_code
    assert status != 200 and status < 500


def test_details_update(client):
    app_id = _setup()
    r = client.post("/a/tok1/details", data={
        "name": "Ana Lopez", "email": "ana@x.es", "phone": "611", "availability": ["afternoon", "weekend"]})
    assert r.status_code == 302
    row = _one("SELECT * FROM applications WHERE id=?", app_id)
    assert (row["email"], row["phone"], row["availability"]) == ("ana@x.es", "611", "afternoon,weekend")


def test_document_upload_and_refusal(client):
    app_id = _setup(status="docs_requested")
    client.post("/a/tok1/document", data={"file_name": "not-a-demo-file.pdf"})
    row = _one("SELECT * FROM applications WHERE id=?", app_id)
    assert row["status"] == "docs_requested" and row["doc_file"] is None

    client.post("/a/tok1/document", data={"file_name": "payslip-demo.pdf"})
    row = _one("SELECT * FROM applications WHERE id=?", app_id)
    assert (row["doc_file"], row["status"]) == ("payslip-demo.pdf", "docs_uploaded")
    assert row["doc_summary"]
    assert _one("SELECT COUNT(*) FROM notifications WHERE application_id IS NULL AND title LIKE 'Document%'")[0] >= 1


def test_booking_waitlist_and_offer_flow(client):
    a = _setup(token="t1", name="A", access=1, status="invited")
    b = _setup(token="t2", name="B", access=1, status="invited")
    c = _setup(token="t3", name="C", access=0, status="docs_approved")
    slot = _slot()
    data = {"slot_id": slot}

    client.post("/a/t3/book", data=data)  # no calendar access
    assert _one("SELECT booked_application_id b FROM slots")["b"] is None

    client.post("/a/t1/book", data=data)
    assert _one("SELECT booked_application_id b FROM slots")["b"] == a
    client.post("/a/t2/book", data=data)  # already taken
    assert _one("SELECT booked_application_id b FROM slots")["b"] == a
    assert _one("SELECT status FROM applications WHERE id=?", b)["status"] == "invited"

    client.post("/a/t2/waitlist/join", data=data)
    assert _one("SELECT COUNT(*) FROM waitlist WHERE application_id=?", b)[0] == 1

    client.post("/a/t1/cancel", data=data)
    s = _one("SELECT * FROM slots")
    assert s["booked_application_id"] is None and s["offer_application_id"] == b
    assert _one("SELECT status FROM applications WHERE id=?", a)["status"] == "invited"

    client.post("/a/t2/offer/accept", data=data)
    s = _one("SELECT * FROM slots")
    assert s["booked_application_id"] == b and s["offer_application_id"] is None
    assert _one("SELECT status FROM applications WHERE id=?", b)["status"] == "booked"
