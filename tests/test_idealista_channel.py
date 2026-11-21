"""Unit A2 tests. No browser, no network: the private agent runners are replaced.

Must prove (DESIGN.md section 12):
- with a non-local inbox URL and an empty allowlist, send_reply raises and opens no browser
"""
import pytest

from housia import config
from housia.channels import idealista
from housia.channels.base import ChannelError
from housia.channels.idealista import Enquiries, Enquiry, IdealistaChannel, SendResult

REMOTE_INBOX = "https://www.idealista.com/es/conversations"


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setattr(config, "BROWSER_MODEL", "test-model")
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(config, "SEND_ALLOWLIST", [])
    return monkeypatch


@pytest.fixture
def sends(monkeypatch):
    """Record calls to the agent runner instead of opening a browser."""
    calls = []

    def fake_send(conversation_id, text):
        calls.append((conversation_id, text))
        return SendResult(conversation_found=True, sent=True)

    monkeypatch.setattr(idealista, "_run_send_agent", fake_send)
    return calls


def test_remote_inbox_empty_allowlist_raises_and_opens_no_browser(settings, sends):
    settings.setattr(config, "IDEALISTA_INBOX_URL", REMOTE_INBOX)

    def no_browser():
        raise AssertionError("a browser was opened")

    settings.setattr(idealista, "_browser", no_browser)
    with pytest.raises(ChannelError, match="contact not on the send allowlist"):
        IdealistaChannel().send_reply("12345", "Hola")
    assert sends == []


def test_allowlisted_contact_passes_the_guard(settings, sends):
    settings.setattr(config, "IDEALISTA_INBOX_URL", REMOTE_INBOX)
    settings.setattr(config, "SEND_ALLOWLIST", ["Team Tester"])
    settings.setattr(idealista, "_run_fetch_agent", lambda: Enquiries(items=[
        Enquiry(conversation_id="c-1", contact_name="team  tester", text="Is it free?",
                received_at="hace 5 minutos"),
        Enquiry(conversation_id="c-2", contact_name="Real Person", text="Hello"),
    ]))
    channel = IdealistaChannel()
    messages = channel.fetch_new_messages()
    assert [m.external_conversation_id for m in messages] == ["c-1", "c-2"]
    assert messages[0].received_at is None  # relative time is not kept, so the id stays stable

    channel.send_reply("c-1", "Yes.\nIt is free.")
    assert sends == [("c-1", "Yes.\nIt is free.")]
    with pytest.raises(ChannelError, match="allowlist"):
        channel.send_reply("c-2", "Hi")
    assert len(sends) == 1


def test_local_inbox_is_not_restricted(settings, sends):
    settings.setattr(config, "IDEALISTA_INBOX_URL", "http://localhost:5000/mock/inbox")
    IdealistaChannel().send_reply("7", "Hola")
    assert sends == [("7", "Hola")]


def test_missing_model_setting_raises(settings, sends):
    settings.setattr(config, "IDEALISTA_INBOX_URL", "http://localhost:5000/mock/inbox")
    settings.setattr(config, "BROWSER_MODEL", None)
    with pytest.raises(ChannelError, match="BROWSER_MODEL"):
        IdealistaChannel().send_reply("7", "Hola")
    with pytest.raises(ChannelError, match="BROWSER_MODEL"):
        IdealistaChannel().fetch_new_messages()
    assert sends == []


def test_unconfirmed_send_raises(settings, monkeypatch):
    settings.setattr(config, "IDEALISTA_INBOX_URL", "http://localhost:5000/mock/inbox")
    calls = []
    monkeypatch.setattr(idealista, "_run_send_agent",
                        lambda cid, text: calls.append(cid) or SendResult(conversation_found=True, sent=False))
    with pytest.raises(ChannelError, match="could not confirm"):
        IdealistaChannel().send_reply("7", "Hola")
    assert calls == ["7"]  # one attempt, no retry
