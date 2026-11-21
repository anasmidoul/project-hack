"""Access rules for requests that arrive through the public tunnel (Cloudflare headers)."""

import pytest

from housia import config, db

PUBLIC = {"Cf-Connecting-Ip": "203.0.113.5", "X-Forwarded-Proto": "https"}
OWNER = ("owner", "correct-horse-battery")
PROTECTED = ["/", "/demo", "/mock/inbox", "/properties/1/conversations/export.csv"]


@pytest.fixture
def seeded(client, monkeypatch):
    monkeypatch.setattr(config, "SECRET_KEY", "test-secret")
    client.post("/demo/reset")  # local request, no password yet
    with db.tx() as conn:
        token = conn.execute("SELECT token FROM applications ORDER BY id LIMIT 1").fetchone()[0]
    return token


def _state():
    with db.tx() as conn:
        offset = conn.execute("SELECT value FROM settings WHERE key='clock_offset_min'").fetchone()
        threads = conn.execute("SELECT COUNT(*) FROM mock_threads").fetchone()[0]
    return (offset[0] if offset else None, threads)


def test_public_without_sign_in_is_refused(client, seeded, monkeypatch):
    monkeypatch.setattr(config, "OWNER_PASSWORD", OWNER[1])
    for path in PROTECTED:
        assert client.get(path, headers=PUBLIC).status_code == 401, path
    client.post("/mock/candidate/send", data={"contact_name": "Marker", "body": "hi"})  # local
    before = _state()
    assert client.post("/demo/reset", headers=PUBLIC).status_code == 401
    assert client.post("/demo/clock", data={"minutes": "60"}, headers=PUBLIC).status_code == 401
    assert _state() == before


def test_public_applicant_pages_and_static_are_open(client, seeded, monkeypatch):
    monkeypatch.setattr(config, "OWNER_PASSWORD", OWNER[1])
    assert client.get(f"/a/{seeded}", headers=PUBLIC).status_code == 200
    assert client.get("/apply/1", headers=PUBLIC).status_code == 200
    assert client.get("/static/favicon.svg", headers=PUBLIC).status_code == 200


def test_public_sign_in(client, seeded, monkeypatch):
    monkeypatch.setattr(config, "OWNER_PASSWORD", OWNER[1])
    assert client.get("/", headers=PUBLIC, auth=OWNER).status_code == 200
    assert client.get("/demo", headers=PUBLIC, auth=OWNER).status_code == 200
    assert client.get("/", headers=PUBLIC, auth=("owner", "wrong")).status_code == 401
    # Signed-in form posts are accepted from this site only.
    same = {**PUBLIC, "Origin": "https://localhost"}
    other = {**PUBLIC, "Origin": "https://evil.example"}
    assert client.post("/demo/clock", data={"minutes": "5"}, headers=other, auth=OWNER).status_code == 403
    assert client.post("/demo/clock", data={"minutes": "5"}, headers=same, auth=OWNER).status_code == 302


def test_public_without_password_configured_is_forbidden(client, seeded, monkeypatch):
    monkeypatch.setattr(config, "OWNER_PASSWORD", None)
    for path in PROTECTED:
        response = client.get(path, headers=PUBLIC)
        assert response.status_code == 403, path
        assert response.mimetype == "text/plain"
    before = _state()
    assert client.post("/demo/reset", headers=PUBLIC).status_code == 403
    assert _state() == before
    assert client.get(f"/a/{seeded}", headers=PUBLIC).status_code == 200
    assert client.get("/apply/1", headers=PUBLIC).status_code == 200


def test_local_requests_unchanged(client, seeded, monkeypatch):
    monkeypatch.setattr(config, "OWNER_PASSWORD", None)
    for path in PROTECTED:
        assert client.get(path).status_code == 200, path
    monkeypatch.setattr(config, "OWNER_PASSWORD", OWNER[1])
    assert client.get("/").status_code == 401
    assert client.get("/", auth=OWNER).status_code == 200
    assert client.get("/mock/inbox").status_code == 200  # browser agent reads it without sign-in
    assert client.get(f"/a/{seeded}").status_code == 200


def test_session_cookie_secure_only_on_https(client, seeded, monkeypatch):
    monkeypatch.setattr(config, "OWNER_PASSWORD", OWNER[1])
    public = client.get("/properties/new", headers=PUBLIC, auth=OWNER).headers.get("Set-Cookie")
    local = client.application.test_client().get("/properties/new", auth=OWNER).headers.get("Set-Cookie")
    assert public and "Secure" in public and "HttpOnly" in public and "SameSite=Lax" in public
    assert local and "Secure" not in local and "HttpOnly" in local and "SameSite=Lax" in local
