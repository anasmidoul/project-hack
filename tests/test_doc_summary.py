"""Unit A8 tests.

Must prove:
- the model receives no real value from the seeded PDF (fake model)
- the saved summary contains the real name again
- a model error still leaves a summary and raises nothing
"""
import pytest

from housia import config, db, llm
from housia.services import doc_summary

NAME = "Lucía Fernández García"
EMAIL = "lucia.fernandez@example.com"
PHONE = "612 345 678"
DNI = "12345678Z"
IBAN = "ES91 2100 0418 4502 0005 1332"

DOC_TEXT = (
    "NÓMINA - PAYSLIP\n"
    "Employer: Acme Logistics SL\n"
    f"Employee {NAME}, DNI {DNI}\n"
    f"Contact: {EMAIL} / {PHONE}\n"
    f"Paid to account {IBAN}\n"
    "Period: October 2026. Net pay: 2.150,00 EUR\n"
)


@pytest.fixture
def app_id(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "HOUSIA_DB", str(tmp_path / "test.db"))
    db.init_db()
    with db.tx() as conn:
        conn.execute(
            "INSERT INTO properties (id, title, address, city, rental_type, rent_eur, "
            "required_document, created_at) VALUES (1, 'Flat', 'Calle 1', 'Madrid', "
            "'residential', 1200, 'Latest payslip', '2026-11-20T10:00:00')"
        )
        conn.execute(
            "INSERT INTO applications (id, property_id, token, name, email, phone, source, "
            "status, doc_file, created_at) VALUES (1, 1, 'tok', ?, ?, ?, 'link', "
            "'docs_uploaded', 'payslip_lucia.pdf', '2026-11-20T10:00:00')",
            (NAME, EMAIL, PHONE),
        )
    monkeypatch.setattr(doc_summary, "_extract_text", lambda path: DOC_TEXT)
    return 1


def _enable_llm(monkeypatch):
    monkeypatch.setattr(config, "REPLY_ENGINE", "llm")
    monkeypatch.setattr(config, "REPLY_MODEL", "fake-model")
    monkeypatch.setattr(config, "OPENAI_API_KEY", "fake-key")


def _state():
    with db.tx() as conn:
        summary = conn.execute("SELECT doc_summary FROM applications WHERE id = 1").fetchone()[0]
        notes = conn.execute(
            "SELECT body FROM notifications WHERE application_id IS NULL"
        ).fetchall()
    return summary, [n["body"] for n in notes]


FALLBACK = "Document received: payslip_lucia.pdf. Automatic check not available."


def test_model_gets_no_real_values_and_summary_has_real_name(app_id, monkeypatch):
    _enable_llm(monkeypatch)
    sent = []

    def fake_model(system, user):
        sent.append(system + "\n" + user)
        assert "[NAME_1]" in user
        return "A payslip. It matches the required document. The name [NAME_1] matches."

    monkeypatch.setattr(llm, "_call_model", fake_model)
    doc_summary.summarize_for_landlord(app_id)

    assert len(sent) == 1
    for value in (NAME, "Lucía", "Fernández", "García", DNI, IBAN, EMAIL, PHONE, "612345678"):
        assert value not in sent[0]
    summary, notes = _state()
    assert NAME in summary and "[NAME_1]" not in summary
    assert notes == [summary]


def test_model_error_leaves_fallback_and_notifies(app_id, monkeypatch):
    _enable_llm(monkeypatch)

    def broken(system, user):
        raise RuntimeError("boom")

    monkeypatch.setattr(llm, "_call_model", broken)
    doc_summary.summarize_for_landlord(app_id)
    assert _state() == (FALLBACK, [FALLBACK])


def test_template_engine_does_not_call_model(app_id, monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "_call_model", lambda *a: calls.append(a) or "x")
    monkeypatch.setattr(llm, "complete", lambda *a, **k: calls.append(a) or "x")
    doc_summary.summarize_for_landlord(app_id)
    assert calls == []
    assert _state() == (FALLBACK, [FALLBACK])


def test_file_outside_demo_folder_is_refused(app_id, monkeypatch):
    _enable_llm(monkeypatch)
    bad = "../../schema.sql"
    with db.tx() as conn:
        conn.execute("UPDATE applications SET doc_file = ? WHERE id = 1", (bad,))

    calls = []
    monkeypatch.setattr(doc_summary, "_extract_text", lambda *a: calls.append(a) or DOC_TEXT)
    monkeypatch.setattr(llm, "complete", lambda *a, **k: calls.append(a) or "x")
    doc_summary.summarize_for_landlord(app_id)
    assert calls == []
    expected = f"Document received: {bad}. Automatic check not available."
    assert _state() == (expected, [expected])
