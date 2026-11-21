import re

import pytest

from housia import config, db, llm

NAME, EMAIL, PHONE, TOKEN = "Lucia Fernandez", "lucia.fernandez@example.com", "612345678", "tok-lucia"
LINK = f"http://localhost:5000/a/{TOKEN}"
SIGNATURE = "This message was written by the landlord's assistant."


@pytest.fixture(autouse=True)
def template_engine(monkeypatch):
    monkeypatch.setattr(config, "REPLY_ENGINE", "template")
    monkeypatch.setattr(config, "OPENAI_API_KEY", None)


def _setup(status="docs_approved", conversation=True, invite_limit=3, others_invited=0):
    with db.tx() as conn:
        conn.execute(
            "INSERT INTO properties (id,title,address,city,rental_type,rent_eur,required_document,"
            "invite_limit,created_at) VALUES (1,'Sunny flat','Calle Mayor 1','Madrid','residential',"
            "1200,'Latest payslip',?,'2026-11-01T10:00:00')", (invite_limit,))
        conn.execute(
            "INSERT INTO applications (id,property_id,token,name,email,phone,source,status,created_at) "
            "VALUES (1,1,?,?,?,?,'mock',?,'2026-11-02T10:00:00')", (TOKEN, NAME, EMAIL, PHONE, status))
        for i in range(others_invited):
            conn.execute(
                "INSERT INTO applications (property_id,token,name,source,status,calendar_access,created_at) "
                "VALUES (1,?,?,'mock','invited',1,'2026-11-02T10:00:00')", (f"other{i}", f"Other {i}"))
        if conversation:
            conn.execute(
                "INSERT INTO conversations (id,property_id,channel,external_id,contact_name,application_id,"
                "created_at) VALUES (1,1,'mock','t1',?,1,'2026-11-02T10:00:00')", (NAME,))


def _state():
    with db.tx() as conn:
        app = conn.execute("SELECT * FROM applications WHERE id=1").fetchone()
        out = conn.execute("SELECT * FROM messages WHERE direction='out'").fetchall()
        mine = conn.execute(
            "SELECT * FROM notifications WHERE application_id=1 AND title='Message from the landlord'"
        ).fetchall()
        landlord = conn.execute("SELECT * FROM notifications WHERE application_id IS NULL").fetchall()
    return app, out, mine, landlord


def test_accept_with_conversation_queues_message(client):
    _setup()
    r = client.post("/applications/1/accept")
    assert r.status_code == 302 and r.headers["Location"].endswith("/applications/1")
    app, out, mine, landlord = _state()
    assert app["status"] == "invited" and app["calendar_access"] == 1
    assert len(out) == 1 and out[0]["status"] == "approved"
    assert LINK in out[0]["body"] and out[0]["body"].endswith(SIGNATURE)
    assert len(mine) == 1 and mine[0]["body"] == out[0]["body"]
    assert len(landlord) == 1
    page = client.get("/applications/1")
    assert page.status_code == 200 and b"Send acceptance" not in page.data


def test_accept_without_conversation_still_notifies(client):
    _setup(status="docs_uploaded", conversation=False)
    client.post("/applications/1/accept")
    app, out, mine, _ = _state()
    assert app["status"] == "invited"
    assert out == []
    assert len(mine) == 1 and LINK in mine[0]["body"]


def test_accept_refused_at_invite_limit(client):
    _setup(invite_limit=1, others_invited=1)
    r = client.post("/applications/1/accept", follow_redirects=True)
    assert b"invite limit" in r.data
    app, out, mine, landlord = _state()
    assert app["status"] == "docs_approved" and app["calendar_access"] == 0
    assert out == [] and mine == [] and landlord == []


def test_decline_closes_without_link_and_only_once(client):
    _setup(status="new")
    client.post("/applications/1/decline")
    app, out, mine, _ = _state()
    assert app["status"] == "closed"
    assert len(out) == 1 and "/a/" not in out[0]["body"] and TOKEN not in out[0]["body"]
    assert out[0]["body"].endswith(SIGNATURE) and len(mine) == 1
    r = client.post("/applications/1/decline", follow_redirects=True)
    assert b"can no longer be declined" in r.data
    _, out, mine, _ = _state()
    assert len(out) == 1 and len(mine) == 1


def test_llm_engine_masks_personal_data_and_falls_back(client, monkeypatch):
    monkeypatch.setattr(config, "REPLY_ENGINE", "llm")
    monkeypatch.setattr(config, "REPLY_MODEL", "fake-model")
    monkeypatch.setattr(config, "OPENAI_API_KEY", "fake-key")
    seen = []

    def fake_model(system, user):
        seen.append(system + "\n" + user)
        placeholder = re.search(r"Applicant name: (\[NAME_\d+\])", user).group(1)
        return f"Dear {placeholder}, you are invited to a viewing. Please pick a time."

    monkeypatch.setattr(llm, "_call_model", fake_model)
    _setup(conversation=True)
    client.post("/applications/1/accept")
    assert len(seen) == 1
    for value in (NAME, "Lucia", "Fernandez", EMAIL, PHONE):
        assert value not in seen[0]
    _, out, _, _ = _state()
    body = out[0]["body"]
    assert body.startswith(f"Dear {NAME}, you are invited")
    assert LINK in body and body.endswith(SIGNATURE)

    def broken(system, user):
        raise RuntimeError("down")

    monkeypatch.setattr(llm, "_call_model", broken)
    with db.tx() as conn:
        conn.execute("INSERT INTO applications (id,property_id,token,name,source,status,created_at) "
                     "VALUES (2,1,'tok2','Marta Ruiz','mock','docs_requested','2026-11-02T10:00:00')")
    client.post("/applications/2/decline")
    with db.tx() as conn:
        note = conn.execute("SELECT body FROM notifications WHERE application_id=2 "
                            "AND title='Message from the landlord'").fetchone()
    assert note["body"].startswith("Hello Marta,\nThank you for your interest in \"Sunny flat\"")
