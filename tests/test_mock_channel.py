"""Unit A1 tests."""
import pytest

from housia import db
from housia.channels.base import ChannelError
from housia.channels.mock import MockChannel


def _post_candidate(client, body="Hello, is it free?", name="Ana", thread_id=""):
    return client.post(
        "/mock/candidate/send",
        data={"thread_id": thread_id, "contact_name": name, "body": body},
    )


def test_candidate_post_creates_thread_and_channel_returns_it(client):
    r = _post_candidate(client)
    assert r.status_code == 302 and r.headers["Location"].endswith("/mock/candidate")
    msgs = MockChannel().fetch_new_messages()
    assert len(msgs) == 1
    assert msgs[0].contact_name == "Ana"
    assert msgs[0].text == "Hello, is it free?"
    assert msgs[0].external_conversation_id.isdigit()


def test_fetched_message_not_returned_twice(client):
    _post_candidate(client)
    ch = MockChannel()
    assert len(ch.fetch_new_messages()) == 1
    assert ch.fetch_new_messages() == []


def test_sent_reply_appears_in_thread(client):
    _post_candidate(client)
    msg = MockChannel().fetch_new_messages()[0]
    MockChannel().send_reply(msg.external_conversation_id, "Yes, it is free.")
    with db.tx() as conn:
        rows = conn.execute(
            "SELECT sender, body FROM mock_messages WHERE thread_id = ? ORDER BY id",
            (int(msg.external_conversation_id),),
        ).fetchall()
    assert [(r["sender"], r["body"]) for r in rows][-1] == ("landlord", "Yes, it is free.")
    # landlord rows are never handed back as incoming
    assert MockChannel().fetch_new_messages() == []


def test_send_reply_unknown_thread_raises(client):
    with pytest.raises(ChannelError):
        MockChannel().send_reply("999", "hi")
