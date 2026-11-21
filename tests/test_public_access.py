"""Access rules for requests that arrive through the public tunnel (Cloudflare headers)."""

import pytest

from housia import config, db

PUBLIC = {"Cf-Connecting-Ip": "203.0.113.5", "X-Forwarded-Proto": "https"}
OWNER = ("owner", "correct-horse-battery")
PROTECTED = ["/", "/guide", "/demo", "/mock/inbox", "/properties/1/conversations/export.csv"]


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
    assert client.get("/guide", headers=PUBLIC, auth=OWNER).status_code == 200
    old = client.get("/demo", headers=PUBLIC, auth=OWNER)  # the old demo page: now the guide
    assert old.status_code == 302 and old.headers["Location"] == "/guide"
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
        assert client.get(path).status_code == (302 if path == "/demo" else 200), path
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


# --- Read-only judge sign-in --------------------------------------------------------------

JUDGE = ("judge", "judges-may-look")
READ_ONLY = "Read-only access: the judge login cannot change anything."


@pytest.fixture
def judge_on(seeded, monkeypatch):
    monkeypatch.setattr(config, "OWNER_PASSWORD", OWNER[1])
    monkeypatch.setattr(config, "JUDGE_PASSWORD", JUDGE[1])
    return seeded


def _dump():
    with db.tx() as conn:
        return list(conn.iterdump())


def test_judge_can_read_owner_pages(client, judge_on):
    for path in ["/", "/properties/1", "/properties/1/conversations", "/guide", "/mock/inbox"]:
        assert client.get(path, headers=PUBLIC, auth=JUDGE).status_code == 200, path
        assert client.head(path, headers=PUBLIC, auth=JUDGE).status_code == 200, path
    assert client.get("/demo", headers=PUBLIC, auth=JUDGE).headers["Location"] == "/guide"


def test_judge_changes_are_refused(client, judge_on):
    with db.tx() as conn:
        app_id = conn.execute("SELECT id FROM applications ORDER BY id LIMIT 1").fetchone()[0]
        slot_id = conn.execute("SELECT id FROM slots ORDER BY id LIMIT 1").fetchone()[0]
    before = _dump()
    back = {**PUBLIC, "Referer": "https://localhost/properties/1?tab=x"}
    for path, data in [
        ("/demo/reset", {}),
        ("/demo/clock", {"minutes": "60"}),
        (f"/applications/{app_id}/document/approve", {}),
        (f"/slots/{slot_id}/cancel", {}),
    ]:
        response = client.post(path, data=data, headers=PUBLIC, auth=JUDGE)
        assert response.status_code == 303, path
        assert response.headers["Location"] == "/", path
    # Back to the page they came from when it is on this site; never to another site.
    response = client.post("/demo/reset", headers=back, auth=JUDGE)
    assert response.headers["Location"] == "/properties/1?tab=x"
    evil = {**PUBLIC, "Referer": "https://evil.example/x"}
    assert client.post("/demo/reset", headers=evil, auth=JUDGE).headers["Location"] == "/"
    # The demo tools on the guide are refused too, and lead back to the guide.
    from_guide = {**PUBLIC, "Referer": "https://localhost/guide"}
    for path, data in [("/demo/clock", {"minutes": "30"}), ("/demo/reset", {})]:
        response = client.post(path, data=data, headers=from_guide, auth=JUDGE)
        assert response.status_code == 303 and response.headers["Location"] == "/guide", path
    assert _dump() == before
    page = client.get("/", headers=PUBLIC, auth=JUDGE).get_data(as_text=True)
    assert READ_ONLY in page


def test_judge_may_write_as_candidate(client, judge_on):
    response = client.post("/mock/candidate/send", data={"contact_name": "Judge", "body": "Is it free?"},
                           headers=PUBLIC, auth=JUDGE)
    assert response.status_code == 302
    with db.tx() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM mock_messages WHERE body = 'Is it free?'"
        ).fetchone()[0] == 1


def test_owner_keeps_full_access_after_judge(client, judge_on):
    client.get("/", headers=PUBLIC, auth=JUDGE)  # same browser signed in as judge first
    response = client.post("/demo/clock", data={"minutes": "45"}, headers=PUBLIC, auth=OWNER)
    assert response.status_code == 302
    assert _state()[0] == "45"
    # Without credentials the browser is not signed in at all, whatever came before.
    assert client.get("/", headers=PUBLIC).status_code == 401


def test_wrong_or_crossed_credentials_are_refused(client, judge_on, monkeypatch):
    for auth in [("judge", "wrong"), ("judge", OWNER[1]), ("owner", JUDGE[1]), ("Judge", JUDGE[1])]:
        assert client.get("/", headers=PUBLIC, auth=auth).status_code == 401, auth
    monkeypatch.setattr(config, "JUDGE_PASSWORD", None)
    assert client.get("/", headers=PUBLIC, auth=JUDGE).status_code == 401
    assert client.get("/", headers=PUBLIC, auth=("judge", "")).status_code == 401
    monkeypatch.setattr(config, "JUDGE_PASSWORD", OWNER[1])  # same as the owner password
    assert client.get("/", headers=PUBLIC, auth=("judge", OWNER[1])).status_code == 401
    assert client.get("/", headers=PUBLIC, auth=OWNER).status_code == 200


def test_judge_label_only_for_judge(client, judge_on):
    assert "Judge view" in client.get("/", headers=PUBLIC, auth=JUDGE).get_data(as_text=True)
    assert "Judge view" not in client.get("/", headers=PUBLIC, auth=OWNER).get_data(as_text=True)


def test_judge_rules_apply_locally_and_applicant_pages_stay_open(client, judge_on):
    assert client.get("/").status_code == 401
    assert client.get("/", auth=JUDGE).status_code == 200
    before = _dump()
    assert client.post("/demo/reset", auth=JUDGE).status_code == 303
    assert _dump() == before
    assert client.get(f"/a/{judge_on}", headers=PUBLIC).status_code == 200
    assert client.get("/apply/1", headers=PUBLIC).status_code == 200
    assert client.get("/static/favicon.svg", headers=PUBLIC).status_code == 200


def test_form_posts_from_a_real_browser_are_not_refused(client, monkeypatch):
    """Browsers send `Origin: null` on form posts when the page says `Referrer-Policy: no-referrer`.
    The pages must use `same-origin`, and a null origin stays refused as a cross-site post."""
    monkeypatch.setattr(config, "OWNER_PASSWORD", "owner-pass-for-test")
    public = {"Cf-Connecting-Ip": "203.0.113.5", "X-Forwarded-Proto": "https"}
    page = client.get("/apply/1", headers=public)
    assert page.headers.get("Referrer-Policy", "same-origin") == "same-origin"
    refused = client.post("/apply/1", data={"name": "Test Person"}, headers={**public, "Origin": "null"})
    assert refused.status_code == 403
    own = "https://" + page.request.host
    accepted = client.post("/apply/1", data={"name": "Test Person"}, headers={**public, "Origin": own})
    assert accepted.status_code in (302, 303)
