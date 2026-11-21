"""Unit A7 tests.

Must prove:
- complete sends only masked text to the model (checked with a fake model) and returns unmasked text
"""
import pytest

from housia import config, llm


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(config, "REPLY_MODEL", "fake-model")
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-test")


def test_complete_sends_masked_and_returns_unmasked(configured, monkeypatch):
    seen = {}

    def fake_model(system, user):
        seen["system"], seen["user"] = system, user
        return "Dear [NAME_1], we will write to [EMAIL_1]."

    monkeypatch.setattr(llm, "_call_model", fake_model)
    answer = llm.complete(
        "You write replies.",
        "From Marta Gil (marta@example.com, 600 000 002, DNI 11223344B): is it free?",
        known={"NAME": "Marta Gil"},
    )
    for secret in ("Marta", "Gil", "marta@example.com", "600 000 002", "11223344B"):
        assert secret not in seen["user"]
    assert seen["system"] == "You write replies."
    assert answer == "Dear Marta Gil, we will write to marta@example.com."


def test_complete_raises_llmerror_on_model_failure(configured, monkeypatch):
    def broken(system, user):
        raise RuntimeError("boom")

    monkeypatch.setattr(llm, "_call_model", broken)
    with pytest.raises(llm.LLMError):
        llm.complete("s", "hello")


def test_complete_raises_llmerror_without_config(configured, monkeypatch):
    monkeypatch.setattr(llm, "_call_model", lambda s, u: pytest.fail("model must not be called"))
    monkeypatch.setattr(config, "OPENAI_API_KEY", None)
    with pytest.raises(llm.LLMError):
        llm.complete("s", "hello")
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(config, "REPLY_MODEL", None)
    with pytest.raises(llm.LLMError):
        llm.complete("s", "hello")
