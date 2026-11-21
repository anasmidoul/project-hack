from datetime import datetime, timedelta

import pytest

from housia import config, core, db
from housia.channels import get_channel
from housia.channels.base import make_message_id


def add_property(conn, invite_limit=3, now=None):
    cur = conn.execute(
        "INSERT INTO properties (title, address, city, rental_type, rent_eur, required_document, "
        "invite_limit, created_at) VALUES ('Flat', 'Calle 1', 'Madrid', 'residential', 1000, "
        "'Latest payslip', ?, ?)",
        (invite_limit, (now or datetime(2026, 11, 1)).isoformat()),
    )
    return cur.lastrowid


def add_application(conn, property_id, status="docs_approved", token=None):
    cur = conn.execute(
        "INSERT INTO applications (property_id, token, name, source, status, created_at) "
        "VALUES (?, ?, 'Ana Test', 'link', ?, '2026-11-01T10:00:00')",
        (property_id, token or f"tok-{status}-{conn.total_changes}", status),
    )
    return cur.lastrowid


# --- db ---------------------------------------------------------------------


@pytest.fixture
def file_db(tmp_path, monkeypatch):
    path = tmp_path / "sub" / "core.db"
    monkeypatch.setattr(config, "HOUSIA_DB", str(path))
    db.init_db()
    return path


def test_init_db_creates_folder_and_is_idempotent(file_db):
    assert file_db.exists()
    db.init_db()  # second call must not fail on existing tables
    conn = db.get_conn()
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        names = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    assert {"properties", "applications", "slots", "settings", "mock_messages"} <= names


def test_tx_commits(file_db):
    with db.tx() as conn:
        core.set_setting(conn, "k", "v")
    with db.tx() as conn:
        assert core.get_setting(conn, "k") == "v"


def test_tx_rolls_back_on_exception(file_db):
    with pytest.raises(core.DomainError):
        with db.tx() as conn:
            core.set_setting(conn, "k", "v")
            raise core.DomainError("boom")
    with db.tx() as conn:
        assert core.get_setting(conn, "k") is None


def test_tx_closes_connection(file_db):
    with db.tx() as conn:
        pass
    with pytest.raises(Exception):
        conn.execute("SELECT 1")


def test_reset_db_recreates_tables(file_db, monkeypatch):
    from housia import seed

    calls = []
    monkeypatch.setattr(seed, "run", lambda conn, now: calls.append(now))
    with db.tx() as conn:
        core.set_setting(conn, "worker_paused", "1")
    db.reset_db()
    with db.tx() as conn:
        assert core.get_setting(conn, "worker_paused") is None
    assert len(calls) == 1 and isinstance(calls[0], datetime)


# --- clock and settings -------------------------------------------------------


def test_now_without_offset_is_real_time(conn):
    assert abs(core.now(conn) - datetime.now()) < timedelta(seconds=5)


def test_now_applies_clock_offset(conn):
    core.set_setting(conn, "clock_offset_min", "90")
    assert abs(core.now(conn) - (datetime.now() + timedelta(minutes=90))) < timedelta(seconds=5)


def test_settings_default_and_overwrite(conn):
    assert core.get_setting(conn, "missing") is None
    assert core.get_setting(conn, "missing", "x") == "x"
    core.set_setting(conn, "worker_paused", "1")
    core.set_setting(conn, "worker_paused", 0)
    assert core.get_setting(conn, "worker_paused") == "0"


# --- notify and status ---------------------------------------------------------


def test_notify_landlord_and_applicant(conn, t0):
    pid = add_property(conn)
    aid = add_application(conn, pid)
    core.notify(conn, property_id=pid, application_id=None, title="L", body="for landlord", now=t0)
    core.notify(conn, property_id=pid, application_id=aid, title="A", body="for applicant", now=t0)
    rows = conn.execute("SELECT * FROM notifications ORDER BY id").fetchall()
    assert [r["application_id"] for r in rows] == [None, aid]
    assert rows[0]["title"] == "L" and rows[0]["body"] == "for landlord"
    assert rows[0]["created_at"] == "2026-11-23T09:00:00"
    assert rows[0]["is_read"] == 0


def test_set_status(conn):
    aid = add_application(conn, add_property(conn), status="new")
    core.set_status(conn, aid, "docs_requested")
    assert conn.execute("SELECT status FROM applications WHERE id=?", (aid,)).fetchone()[0] == "docs_requested"
    with pytest.raises(core.DomainError):
        core.set_status(conn, aid, "nonsense")
    with pytest.raises(core.DomainError):
        core.set_status(conn, 999, "new")


# --- time bands ------------------------------------------------------------------


def test_time_band(t0):
    assert t0.weekday() == 0 and t0.hour == 9
    assert core.time_band(t0) == "morning"
    assert core.time_band(t0.replace(hour=13, minute=59)) == "morning"
    assert core.time_band(t0.replace(hour=14)) == "afternoon"
    assert core.time_band(t0.replace(hour=19)) == "afternoon"
    assert core.time_band(t0 + timedelta(days=5)) == "weekend"  # Saturday morning
    assert core.time_band(t0 + timedelta(days=6, hours=8)) == "weekend"  # Sunday afternoon
    assert core.time_band("2026-11-23T15:00:00") == "afternoon"
    assert set(core.TIME_BANDS) == {"morning", "afternoon", "weekend"}


def test_applicant_url(monkeypatch):
    monkeypatch.setattr(config, "BASE_URL", "http://example.test/")
    assert core.applicant_url("abc") == "http://example.test/a/abc"


# --- calendar access ---------------------------------------------------------------


@pytest.mark.parametrize("status", ["docs_uploaded", "docs_approved"])
def test_grant_calendar_access_allowed(conn, t0, status):
    pid = add_property(conn)
    aid = add_application(conn, pid, status=status)
    core.grant_calendar_access(conn, aid, "landlord", t0)
    app = conn.execute("SELECT * FROM applications WHERE id=?", (aid,)).fetchone()
    assert app["calendar_access"] == 1
    assert app["invited_by"] == "landlord"
    assert app["status"] == "invited"
    assert core.invited_count(conn, pid) == 1
    notes = conn.execute("SELECT * FROM notifications WHERE application_id=?", (aid,)).fetchall()
    assert len(notes) == 1
    assert notes[0]["property_id"] == pid
    assert core.applicant_url(app["token"]) in notes[0]["body"]
    landlord_notes = conn.execute("SELECT COUNT(*) FROM notifications WHERE application_id IS NULL").fetchone()[0]
    assert landlord_notes == 0


def test_grant_calendar_access_auto(conn, t0):
    aid = add_application(conn, add_property(conn))
    core.grant_calendar_access(conn, aid, "auto", t0)
    assert conn.execute("SELECT invited_by FROM applications WHERE id=?", (aid,)).fetchone()[0] == "auto"


@pytest.mark.parametrize(
    "status",
    [s for s in core.APPLICATION_STATUSES if s not in ("docs_uploaded", "docs_approved")],
)
def test_grant_calendar_access_wrong_status(conn, t0, status):
    aid = add_application(conn, add_property(conn), status=status)
    with pytest.raises(core.DomainError):
        core.grant_calendar_access(conn, aid, "landlord", t0)
    app = conn.execute("SELECT * FROM applications WHERE id=?", (aid,)).fetchone()
    assert app["status"] == status and app["calendar_access"] == 0
    assert conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0] == 0


def test_grant_calendar_access_invite_limit(conn, t0):
    pid = add_property(conn, invite_limit=2)
    first, second, third = (add_application(conn, pid) for _ in range(3))
    core.grant_calendar_access(conn, first, "landlord", t0)
    core.grant_calendar_access(conn, second, "auto", t0)
    with pytest.raises(core.DomainError):
        core.grant_calendar_access(conn, third, "landlord", t0)
    app = conn.execute("SELECT * FROM applications WHERE id=?", (third,)).fetchone()
    assert app["status"] == "docs_approved" and app["calendar_access"] == 0
    assert core.invited_count(conn, pid) == 2


def test_invited_count_is_per_property(conn, t0):
    p1, p2 = add_property(conn), add_property(conn)
    core.grant_calendar_access(conn, add_application(conn, p1), "landlord", t0)
    assert core.invited_count(conn, p1) == 1
    assert core.invited_count(conn, p2) == 0


def test_grant_calendar_access_missing_application(conn, t0):
    with pytest.raises(core.DomainError):
        core.grant_calendar_access(conn, 404, "landlord", t0)


# --- channels ---------------------------------------------------------------------


def test_make_message_id_is_stable():
    a = make_message_id("conv-1", "Hello, is it free?", "2026-11-23T09:00:00")
    assert a == make_message_id("conv-1", "Hello, is it free?", "2026-11-23T09:00:00")
    assert a == make_message_id("conv-1", "  Hello,  is it free?\n", "2026-11-23T09:00:00")
    assert len(a) == 40 and int(a, 16) >= 0
    assert a != make_message_id("conv-2", "Hello, is it free?", "2026-11-23T09:00:00")
    assert a != make_message_id("conv-1", "Hello, is it free?", None)
    assert a != make_message_id("conv-1", "Other text", "2026-11-23T09:00:00")


def test_get_channel_unknown():
    with pytest.raises(ValueError):
        get_channel("myspace")


def test_browser_use_telemetry_is_forced_off():
    """Agent results contain personal data; browser-use must never send them as telemetry."""
    import os

    from housia import config  # noqa: F401  (importing it applies the setting)

    assert os.environ["ANONYMIZED_TELEMETRY"] == "false"
