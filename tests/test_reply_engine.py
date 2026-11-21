"""Unit A4 tests."""
from housia import config, llm
from housia.services.reply_engine import generate_reply

PROP = {
    "title": "Sunny flat", "address": "Calle Mayor 1", "city": "Madrid",
    "rental_type": "residential", "rent_eur": 950, "description": "",
    "facts": "Small dogs are allowed.\nDeposit is two months of rent.",
    "required_document": "Latest payslip",
}
LINK = "http://x/apply/tok"
PRIOR = [{"direction": "in", "body": "hi"}, {"direction": "out", "body": "hello"}]


def test_first_contact_has_link_and_document(monkeypatch):
    monkeypatch.setattr(config, "REPLY_ENGINE", "template")
    r = generate_reply(PROP, [], "Is it available?", "Ana", LINK)
    assert LINK in r.text and "Latest payslip" in r.text and "Ana" in r.text
    assert "950" in r.text and "Madrid" in r.text and "long-term" in r.text
    assert "landlord's assistant" in r.text and not r.needs_landlord


def test_unknown_question_needs_landlord(monkeypatch):
    monkeypatch.setattr(config, "REPLY_ENGINE", "template")
    r = generate_reply(PROP, PRIOR, "Is there a balcony garden?", "Ana", LINK)
    assert r.needs_landlord and r.reason
    assert "check with the landlord" in r.text


def test_fact_is_quoted(monkeypatch):
    monkeypatch.setattr(config, "REPLY_ENGINE", "template")
    r = generate_reply(PROP, PRIOR, "Can I bring my dog?", "Ana", LINK)
    assert "Small dogs are allowed." in r.text and not r.needs_landlord


def test_llm_failure_falls_back(monkeypatch):
    monkeypatch.setattr(config, "REPLY_ENGINE", "llm")

    def boom(*a, **k):
        raise llm.LLMError("down")
    monkeypatch.setattr(llm, "complete", boom)
    r = generate_reply(PROP, [], "Hello", "Ana", LINK)
    assert LINK in r.text and "Latest payslip" in r.text


def test_llm_unknown_flags(monkeypatch):
    monkeypatch.setattr(config, "REPLY_ENGINE", "llm")
    monkeypatch.setattr(llm, "complete", lambda s, u, known=None: "UNKNOWN")
    r = generate_reply(PROP, PRIOR, "Is there a gym?", "Ana", LINK)
    assert r.needs_landlord


def test_llm_first_contact_unknown_gets_template_reply(monkeypatch):
    monkeypatch.setattr(config, "REPLY_ENGINE", "llm")
    monkeypatch.setattr(llm, "complete", lambda s, u, known=None: "UNKNOWN")
    r = generate_reply(PROP, [], "Hi, is the room still available?", "Ana", LINK)
    assert LINK in r.text and "Latest payslip" in r.text and not r.needs_landlord


def test_template_still_available_answers_yes(monkeypatch):
    r = generate_reply(PROP, PRIOR, "Is it still available?", "Ana", LINK)
    assert "Yes, it is still available." in r.text and not r.needs_landlord
    rented = dict(PROP, contract_status="signed")
    r = generate_reply(rented, PRIOR, "Is it still available?", "Ana", LINK)
    assert "just been rented" in r.text and not r.needs_landlord
    r = generate_reply(rented, [], "Hi", "Ana", LINK)
    assert LINK not in r.text and "payslip" not in r.text


def test_llm_first_contact_appends_missing_link(monkeypatch):
    monkeypatch.setattr(config, "REPLY_ENGINE", "llm")
    monkeypatch.setattr(llm, "complete", lambda s, u, known=None: "Hello Ana, yes it is free.")
    r = generate_reply(PROP, [], "Hi", "Ana", LINK)
    assert LINK in r.text and r.text.endswith("assistant.") and not r.needs_landlord
