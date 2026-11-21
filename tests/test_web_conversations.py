"""Unit A5 tests: landlord conversation routes."""
from contextlib import contextmanager

import pytest
from flask import template_rendered

from housia import core, db
from housia.channels.base import IncomingMessage
from housia.services import conversations


@contextmanager
def captured_templates(app):
    recorded = []

    def record(sender, template, context, **extra):
        recorded.append((template.name, context))

    template_rendered.connect(record, app)
    try:
        yield recorded
    finally:
        template_rendered.disconnect(record, app)


@pytest.fixture
def thread(client, t0):
    """One property, an application, a conversation with one incoming message and a draft."""
    with db.tx() as conn:
        conn.execute(
            "INSERT INTO properties (id, title, address, city, rental_type, rent_eur, "
            "required_document, created_at) VALUES (1, 'Flat', 'Calle 1', 'Madrid', "
            "'residential', 900, 'Payslip', ?)", (t0.isoformat(),))
        app_id = conn.execute(
            "INSERT INTO applications (property_id, token, name, source, created_at) "
            "VALUES (1, 'tok1', 'Ana Lopez', 'mock', ?)", (t0.isoformat(),)).lastrowid
        in_id = conversations.record_incoming(
            conn, "mock", IncomingMessage("7", "m1", "Ana Lopez", "Do you allow pets?"), 1, t0)
        conv_id = conn.execute("SELECT id FROM conversations").fetchone()["id"]
        conversations.link_application(conn, conv_id, app_id)
        draft_id = conversations.save_outgoing(conn, conv_id, "Let me check.", "draft", in_id,
                                               "Asked about pets", t0)
        conversations.set_conversation_status(conn, conv_id, "needs_landlord")
    return {"conv": conv_id, "in": in_id, "draft": draft_id, "app": app_id}


def _row(sql, *args):
    with db.tx() as conn:
        return conn.execute(sql, args).fetchone()


def test_pages_load_with_data(client, thread):
    with captured_templates(client.application) as rendered:
        assert client.get("/properties/1/conversations").status_code == 200
        assert client.get(f"/conversations/{thread['conv']}").status_code == 200
    (_, listing), (_, detail) = rendered
    assert listing["property"]["id"] == 1
    assert [c["id"] for c in listing["conversations"]] == [thread["conv"]]
    assert listing["conversations"][0]["pending_drafts"] == 1
    assert detail["conversation"]["id"] == thread["conv"]
    assert [m["id"] for m in detail["messages"]] == [thread["in"], thread["draft"]]
    assert detail["application"]["id"] == thread["app"]
    assert client.get("/properties/99/conversations").status_code == 404
    assert client.get("/conversations/99").status_code == 404


def test_approve_with_edit_sets_approved_and_reopens(client, thread):
    r = client.post(f"/messages/{thread['draft']}/approve", data={"body": "No pets, sorry."})
    assert r.status_code == 302 and r.headers["Location"].endswith(f"/conversations/{thread['conv']}")
    msg = _row("SELECT status, body FROM messages WHERE id = ?", thread["draft"])
    assert (msg["status"], msg["body"]) == ("approved", "No pets, sorry.")
    assert _row("SELECT status FROM conversations")["status"] == "open"
    # Approving again is a rule violation: flashed, nothing changes.
    client.post(f"/messages/{thread['draft']}/approve")
    assert _row("SELECT status FROM messages WHERE id = ?", thread["draft"])["status"] == "approved"


def test_discard_stops_redraft_and_manual_reply_attaches(client, thread):
    r = client.post(f"/messages/{thread['draft']}/discard")
    assert r.headers["Location"].endswith(f"/conversations/{thread['conv']}")
    assert _row("SELECT status FROM conversations")["status"] == "open"
    with db.tx() as conn:
        assert conversations.unanswered(conn, "mock") == []  # the worker will not redraft

    client.post(f"/conversations/{thread['conv']}/reply", data={"body": "   "})
    assert _row("SELECT COUNT(*) FROM messages")[0] == 2  # empty reply rejected

    client.post(f"/conversations/{thread['conv']}/reply", data={"body": "Small pets are fine."})
    manual = _row("SELECT * FROM messages ORDER BY id DESC LIMIT 1")
    assert (manual["status"], manual["in_reply_to"]) == ("approved", thread["in"])


def test_pause_sets_setting_and_returns_to_referrer(client):
    r = client.post("/worker/pause", data={"paused": "1"},
                    headers={"Referer": "http://localhost/properties/1/conversations"})
    assert r.headers["Location"].endswith("/properties/1/conversations")
    with db.tx() as conn:
        assert core.get_setting(conn, "worker_paused") == "1"
    r = client.post("/worker/pause", data={"paused": "0"})
    assert r.headers["Location"] == "/"
    with db.tx() as conn:
        assert core.get_setting(conn, "worker_paused") == "0"
