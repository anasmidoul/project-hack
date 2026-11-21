"""Block 1 end-to-end: mock portal -> worker -> template reply engine -> mock portal.

Real mock channel, conversations service, worker and template reply engine. Only
applications.create_application is faked (another unit, still a stub).
"""
import uuid

import pytest

from housia import config, core, db, worker
from housia.channels.mock import MockChannel
from housia.services import applications


def _fake_create_application(conn, property_id, data, source, now):
    return conn.execute(
        "INSERT INTO applications (property_id, token, name, source, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (property_id, uuid.uuid4().hex, data["name"], source, now.isoformat()),
    ).lastrowid


@pytest.fixture
def portal(client, monkeypatch, t0):
    """Returns a function that sets the property's reply mode."""
    monkeypatch.setattr(config, "REPLY_ENGINE", "template")
    monkeypatch.setattr(config, "DEFAULT_PROPERTY_ID", 1)
    monkeypatch.setattr(applications, "create_application", _fake_create_application)

    def setup(mode):
        with db.tx() as conn:
            conn.execute(
                "INSERT INTO properties (id, title, address, city, rental_type, rent_eur, "
                "required_document, reply_mode, listing_ref, created_at) VALUES (1, 'Flat', "
                "'Calle 1', 'Madrid', 'residential', 900, 'Latest payslip', ?, 'L-1', ?)",
                (mode, t0.isoformat()))
        r = client.post("/mock/candidate/send", data={
            "thread_id": "", "contact_name": "Ana", "body": "Hello, is the flat available?"})
        assert r.status_code == 302
    return setup


def _landlord_messages():
    with db.tx() as conn:
        return [r["body"] for r in conn.execute(
            "SELECT body FROM mock_messages WHERE sender = 'landlord' ORDER BY id")]


def _token():
    with db.tx() as conn:
        return conn.execute("SELECT token FROM applications").fetchone()["token"]


def test_automatic_mode_replies_once_with_applicant_link(portal):
    portal("automatic")

    counts = worker.run_once(MockChannel())
    again = worker.run_once(MockChannel())

    assert counts["errors"] == 0 and counts["sent"] == 1
    replies = _landlord_messages()
    assert len(replies) == 1
    assert core.applicant_url(_token()) in replies[0]
    assert again["sent"] == 0 and again["drafted"] == 0 and again["approved"] == 0
    assert len(_landlord_messages()) == 1


def test_assisted_mode_sends_only_after_approval(portal, client):
    portal("assisted")

    counts = worker.run_once(MockChannel())
    assert counts["errors"] == 0 and counts["drafted"] == 1
    assert _landlord_messages() == []
    with db.tx() as conn:
        draft = conn.execute("SELECT * FROM messages WHERE status = 'draft'").fetchone()
    assert draft is not None

    client.post(f"/messages/{draft['id']}/approve")
    worker.run_once(MockChannel())

    assert _landlord_messages() == [draft["body"]]
