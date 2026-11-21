"""Private guest demos: one sandbox database per guest browser (housia/sandbox.py)."""

import os
import time

import pytest

from housia import config, db, sandbox, worker

PUBLIC = {"Cf-Connecting-Ip": "203.0.113.5", "X-Forwarded-Proto": "https"}
SAME = {**PUBLIC, "Origin": "https://localhost"}
CODE = "share-this-demo-code"
OWNER = ("owner", "correct-horse-battery")
JUDGE = ("judge", "judges-may-look")
LABEL = "Your private demo · changes are only visible to you"


@pytest.fixture
def guest_on(client, monkeypatch):
    client.post("/demo/reset")  # seed the main database (local, no password yet)
    monkeypatch.setattr(config, "OWNER_PASSWORD", OWNER[1])
    monkeypatch.setattr(config, "JUDGE_PASSWORD", JUDGE[1])
    monkeypatch.setattr(config, "GUEST_LINK_CODE", CODE)
    return client


def _join(browser):
    response = browser.get(f"/guest/{CODE}", headers=PUBLIC)
    assert response.status_code == 302 and response.headers["Location"] == "/guide"
    with browser.session_transaction() as s:
        return s[sandbox.SESSION_KEY]


def _clock(path=None):
    with db.using(path), db.tx() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key='clock_offset_min'").fetchone()
        return row[0] if row else None


def _main_dump():
    with db.using(None), db.tx() as conn:
        return list(conn.iterdump())


def _files():
    return sorted(p.name for p in sandbox.sandbox_dir().glob("*.db"))


def test_guest_link_codes(guest_on, monkeypatch):
    _join(guest_on)
    assert len(_files()) == 1
    other = guest_on.application.test_client()
    assert other.get("/guest/wrong-code", headers=PUBLIC).status_code == 404
    monkeypatch.setattr(config, "SECRET_KEY", "dev")
    assert other.get(f"/guest/{CODE}", headers=PUBLIC).status_code == 404
    monkeypatch.setattr(config, "SECRET_KEY", "test-secret-key")
    monkeypatch.setattr(config, "GUEST_LINK_CODE", None)
    assert other.get(f"/guest/{CODE}", headers=PUBLIC).status_code == 404
    assert len(_files()) == 1


def test_guest_uses_owner_pages_through_tunnel(guest_on):
    sid = _join(guest_on)
    main_before = _main_dump()
    page = guest_on.get("/", headers=PUBLIC)
    assert page.status_code == 200 and LABEL in page.get_data(as_text=True)
    guide = guest_on.get("/guide", headers=PUBLIC)
    assert guide.status_code == 200 and "This is your own copy of the demo" in guide.get_data(as_text=True)
    assert guest_on.get("/demo", headers=PUBLIC).headers["Location"] == "/guide"
    from_guide = {**SAME, "Referer": "https://localhost/guide"}
    response = guest_on.post("/demo/clock", data={"minutes": "30"}, headers=from_guide)
    assert response.status_code == 302 and response.headers["Location"] == "/guide"
    assert _clock(sandbox.path_for(sid)) == "30"
    assert db.db_path() == db.main_db_path()  # the request's choice does not outlive it
    # The same-origin rule still applies to guests.
    evil = {**PUBLIC, "Origin": "https://evil.example"}
    assert guest_on.post("/demo/clock", data={"minutes": "5"}, headers=evil).status_code == 403
    assert _clock(sandbox.path_for(sid)) == "30"
    assert _main_dump() == main_before


def test_guests_are_isolated(guest_on):
    other = guest_on.application.test_client()
    a, b = _join(guest_on), _join(other)
    assert a != b
    guest_on.post("/demo/clock", data={"minutes": "30"}, headers=SAME)
    other.post("/demo/clock", data={"minutes": "45"}, headers=SAME)
    assert _clock(sandbox.path_for(a)) == "30"
    assert _clock(sandbox.path_for(b)) == "45"
    assert _clock() is None


def test_guest_reset_rebuilds_only_their_sandbox(guest_on):
    sid = _join(guest_on)
    main_before = _main_dump()
    guest_on.post("/demo/clock", data={"minutes": "30"}, headers=SAME)
    assert guest_on.post("/demo/reset", headers=SAME).status_code == 302
    assert _clock(sandbox.path_for(sid)) is None
    with db.using(sandbox.path_for(sid)), db.tx() as conn:
        tokens = [r[0] for r in conn.execute("SELECT token FROM applications")]
    assert tokens and not any(t.startswith("demo-") for t in tokens)  # never the main's tokens
    assert _main_dump() == main_before


def test_applicant_page_uses_the_sandbox(guest_on):
    sid = _join(guest_on)
    with db.using(sandbox.path_for(sid)), db.tx() as conn:
        prop_id, token = conn.execute("SELECT property_id, token FROM applications ORDER BY id LIMIT 1").fetchone()
        conn.execute("UPDATE properties SET title = 'Sandbox Flat' WHERE id = ?", (prop_id,))
    page = guest_on.get(f"/a/{token}", headers=PUBLIC)
    assert page.status_code == 200 and "Sandbox Flat" in page.get_data(as_text=True)
    # Another device without the guest session uses the main database: the token is unknown there.
    stranger = guest_on.application.test_client()
    assert stranger.get(f"/a/{token}", headers=PUBLIC).status_code != 200


def test_deleted_sandbox_is_replaced(guest_on):
    old = _join(guest_on)
    main_before = _main_dump()
    sandbox.delete(sandbox.path_for(old))
    assert guest_on.post("/demo/clock", data={"minutes": "15"}, headers=SAME).status_code == 302
    with guest_on.session_transaction() as s:
        new = s[sandbox.SESSION_KEY]
    assert new != old and _files() == [f"{new}.db"]
    assert _clock(sandbox.path_for(new)) == "15"
    assert _main_dump() == main_before


def test_sandbox_id_validation(guest_on):
    folder = sandbox.sandbox_dir().resolve()
    good = "A" * 31 + "_"
    assert sandbox.path_for(good) == folder / f"{good}.db"
    for bad in [None, 42, "", "A" * 31, "A" * 33, "../" + "A" * 29, "A" * 30 + "/.", "A" * 31 + "."]:
        assert sandbox.path_for(bad) is None, bad
    # A forged-looking session value is never used as a path: the browser gets a fresh sandbox.
    main_before = _main_dump()
    with guest_on.session_transaction() as s:
        s[sandbox.SESSION_KEY] = "../../housia"
    assert guest_on.post("/demo/clock", data={"minutes": "10"}, headers=SAME).status_code == 302
    with guest_on.session_transaction() as s:
        assert sandbox.is_valid_id(s[sandbox.SESSION_KEY])
    assert _main_dump() == main_before


def test_owner_and_judge_use_main_database(guest_on):
    sid = _join(guest_on)
    page = guest_on.get("/", headers=PUBLIC, auth=OWNER).get_data(as_text=True)
    assert LABEL not in page
    assert guest_on.post("/demo/clock", data={"minutes": "20"}, headers=SAME, auth=OWNER).status_code == 302
    assert _clock() == "20" and _clock(sandbox.path_for(sid)) is None
    main_before = _main_dump()
    assert guest_on.post("/demo/clock", data={"minutes": "5"}, headers=SAME, auth=JUDGE).status_code == 303
    assert _main_dump() == main_before and _clock(sandbox.path_for(sid)) is None
    # Wrong credentials are not a sign-in: the browser stays a guest in its sandbox.
    assert guest_on.get("/", headers=PUBLIC, auth=("owner", "wrong")).status_code == 200


def test_worker_answers_in_the_guest_sandbox(guest_on):
    sid = _join(guest_on)
    with db.using(None), db.tx() as conn:
        main_conversations = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
    response = guest_on.post("/mock/candidate/send", headers=SAME,
                             data={"contact_name": "Guest Tester", "body": "Is it still available?"})
    assert response.status_code == 302
    totals = worker.run_sandboxes()
    assert totals["sandboxes"] == 1 and totals["errors"] == 0
    with db.using(sandbox.path_for(sid)), db.tx() as conn:
        replies = conn.execute(
            "SELECT COUNT(*) FROM messages m JOIN conversations c ON c.id = m.conversation_id "
            "WHERE c.contact_name = 'Guest Tester' AND m.direction = 'out'").fetchone()[0]
    assert replies == 1
    with db.using(None), db.tx() as conn:
        assert conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == main_conversations


def test_sandbox_limit_and_cleanup(guest_on, monkeypatch):
    monkeypatch.setattr(config, "SANDBOX_MAX", 2)
    browsers = [guest_on.application.test_client() for _ in range(3)]
    _join(browsers[0]), _join(browsers[1])
    full = browsers[2].get(f"/guest/{CODE}", headers=PUBLIC)
    assert full.status_code == 503 and "The demo is full" in full.get_data(as_text=True)
    assert len(_files()) == 2
    # Idle for more than 30 minutes: the least recently used one makes room.
    old = time.time() - 31 * 60
    for name in _files():
        os.utime(sandbox.sandbox_dir() / name, (old, old))
    _join(browsers[2])
    assert len(_files()) == 2
    # Sandboxes unused for 12 hours are removed with their side files.
    stale = time.time() - 13 * 3600
    for name in _files():
        path = sandbox.sandbox_dir() / name
        (sandbox.sandbox_dir() / f"{name}-wal").write_bytes(b"")
        os.utime(path, (stale, stale))
    assert sandbox.cleanup_stale() == 2
    assert list(sandbox.sandbox_dir().iterdir()) == []
