"""Unit A3 tests.

Must prove:
- a message recorded twice yields one row               (also tests/test_conversations.py)
- a second reply to the same incoming message is rejected (tests/test_conversations.py)
- assisted mode saves a draft and sends nothing
- a flagged reply is never sent
- a failed send is not retried
"""
import uuid
from datetime import datetime

import pytest

from housia import config, core, db, worker
from housia.channels.base import ChannelError, IncomingMessage
from housia.services import applications, reply_engine
from housia.services.reply_engine import ReplyDecision


class FakeChannel:
    name = "mock"

    def __init__(self, messages=(), fail=False):
        self.messages = list(messages)
        self.fail = fail
        self.sent = []
        self.attempts = 0

    def fetch_new_messages(self):
        out, self.messages = self.messages, []
        return out

    def send_reply(self, external_conversation_id, text):
        self.attempts += 1
        if self.fail:
            raise ChannelError("portal down")
        self.sent.append((external_conversation_id, text))


def _fake_create_application(conn, property_id, data, source, now):
    return conn.execute(
        "INSERT INTO applications (property_id, token, name, source, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (property_id, uuid.uuid4().hex, data["name"], source, now.isoformat()),
    ).lastrowid


@pytest.fixture
def setup(tmp_path, monkeypatch):
    """File database with one property; returns a function to set its reply mode."""
    monkeypatch.setattr(config, "HOUSIA_DB", str(tmp_path / "worker.db"))
    monkeypatch.setattr(config, "DEFAULT_PROPERTY_ID", 1)
    monkeypatch.setattr(applications, "create_application", _fake_create_application)
    db.init_db()
    with db.tx() as conn:
        conn.execute(
            "INSERT INTO properties (id, title, address, city, rental_type, rent_eur, "
            "required_document, created_at) VALUES (1, 'Flat', 'Calle 1', 'Madrid', "
            "'residential', 900, 'Payslip', ?)", (datetime(2026, 11, 23, 9).isoformat(),))

    def reply(text="Hi!", needs_landlord=False, reason="", mode="assisted"):
        with db.tx() as conn:
            conn.execute("UPDATE properties SET reply_mode = ?", (mode,))
        monkeypatch.setattr(reply_engine, "generate_reply",
                            lambda *a, **k: ReplyDecision(text, needs_landlord, reason))
    return reply


def _messages():
    with db.tx() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM messages ORDER BY id")]


def _incoming(mid="m1"):
    return IncomingMessage("c1", mid, "Ana Lopez", "Is it available?")


def test_assisted_mode_saves_draft_and_sends_nothing(setup):
    setup(mode="assisted")
    channel = FakeChannel([_incoming(), _incoming()])  # same message twice

    counts = worker.run_once(channel)
    worker.run_once(channel)

    assert counts["recorded"] == 1 and counts["drafted"] == 1 and counts["sent"] == 0
    assert channel.attempts == 0
    assert [(m["direction"], m["status"]) for m in _messages()] == [("in", "received"),
                                                                    ("out", "draft")]
    with db.tx() as conn:
        conv = conn.execute("SELECT * FROM conversations").fetchone()
        assert conv["application_id"] is not None
        assert conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0] == 1


def test_flagged_reply_is_never_sent_even_in_automatic_mode(setup):
    setup(mode="automatic", needs_landlord=True, reason="Asked about pets")
    channel = FakeChannel([_incoming()])

    worker.run_once(channel)
    worker.run_once(channel)

    assert channel.attempts == 0
    out = _messages()[1]
    assert out["status"] == "draft" and out["note"] == "Asked about pets"
    with db.tx() as conn:
        assert conn.execute("SELECT status FROM conversations").fetchone()[0] == "needs_landlord"


def test_automatic_reply_is_sent_once(setup):
    setup(mode="automatic", text="Hello Ana")
    channel = FakeChannel([_incoming()])

    counts = worker.run_once(channel)
    worker.run_once(channel)

    assert counts["approved"] == 1 and counts["sent"] == 1
    assert channel.sent == [("c1", "Hello Ana")]
    assert _messages()[1]["status"] == "sent"


def test_failed_send_is_marked_and_not_retried(setup):
    setup(mode="automatic")
    channel = FakeChannel([_incoming()], fail=True)

    counts = worker.run_once(channel)
    again = worker.run_once(channel)

    assert counts["failed"] == 1 and again["failed"] == 0 and again["drafted"] == 0
    assert channel.attempts == 1
    out = _messages()[1]
    assert out["status"] == "failed" and "portal down" in out["note"]


def test_paused_worker_does_nothing(setup):
    setup(mode="automatic")
    with db.tx() as conn:
        core.set_setting(conn, "worker_paused", "1")
    channel = FakeChannel([_incoming()])

    assert worker.run_once(channel)["paused"] is True
    assert len(channel.messages) == 1 and _messages() == []
