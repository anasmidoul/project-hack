"""Unit A3 tests.

Must prove:
- a message recorded twice yields one row
- a second reply to the same incoming message is rejected
- assisted mode saves a draft and sends nothing        (tests/test_worker.py)
- a flagged reply is never sent                        (tests/test_worker.py)
- a failed send is not retried                         (tests/test_worker.py)
"""
import pytest

from housia import core
from housia.channels.base import IncomingMessage
from housia.services import conversations


@pytest.fixture
def prop_id(conn, t0):
    cur = conn.execute(
        "INSERT INTO properties (title, address, city, rental_type, rent_eur, required_document, "
        "created_at) VALUES ('Flat', 'Calle 1', 'Madrid', 'residential', 900, 'Payslip', ?)",
        (t0.isoformat(),),
    )
    return cur.lastrowid


def _msg(mid="m1", text="Hello, is it available?"):
    return IncomingMessage("c1", mid, "Ana Lopez", text)


def test_message_recorded_twice_yields_one_row(conn, prop_id, t0):
    first = conversations.record_incoming(conn, "mock", _msg(), prop_id, t0)
    second = conversations.record_incoming(conn, "mock", _msg(), prop_id, t0)

    assert first is not None and second is None
    assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == 1
    assert [r["id"] for r in conversations.unanswered(conn, "mock")] == [first]


def test_second_live_reply_rejected_and_discard_hands_over(conn, prop_id, t0):
    in_id = conversations.record_incoming(conn, "mock", _msg(), prop_id, t0)
    conv_id = conversations.get_thread(conn, 1)[0]["conversation_id"]
    draft = conversations.save_outgoing(conn, conv_id, "Hi Ana", "draft", in_id, None, t0)

    with pytest.raises(core.DomainError):
        conversations.save_outgoing(conn, conv_id, "Hi again", "approved", in_id, None, t0)
    assert conversations.unanswered(conn, "mock") == []

    conversations.discard(conn, draft)
    # Discarding means the landlord takes over: the worker must not draft again.
    assert conversations.unanswered(conn, "mock") == []
    # The landlord can still reply by hand to the same message.
    conversations.save_outgoing(conn, conv_id, "Hi again", "approved", in_id, None, t0)
    pending = conversations.pending_to_send(conn, "mock")
    assert [(r["body"], r["external_id"]) for r in pending] == [("Hi again", "c1")]
    listed = conversations.list_conversations(conn, prop_id)
    assert listed[0]["last_message"] == "Hi again" and listed[0]["pending_drafts"] == 0
