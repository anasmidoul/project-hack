from datetime import timedelta

import pytest

from housia import core, seed
from housia.services import scheduling


def test_double_booking_is_rejected_without_changing_slot(conn, t0):
    seed.run(conn, t0)
    first, second = [row[0] for row in conn.execute(
        "SELECT id FROM applications WHERE property_id=1 AND status='docs_approved' ORDER BY created_at LIMIT 2"
    )]
    core.grant_calendar_access(conn, first, "landlord", t0)
    core.grant_calendar_access(conn, second, "landlord", t0)
    slot = conn.execute("SELECT id FROM slots WHERE property_id=1 ORDER BY starts_at LIMIT 1").fetchone()[0]
    scheduling.book(conn, first, slot, t0)
    with pytest.raises(core.DomainError):
        scheduling.book(conn, second, slot, t0)
    assert conn.execute("SELECT booked_application_id FROM slots WHERE id=?", (slot,)).fetchone()[0] == first
    assert conn.execute("SELECT status FROM applications WHERE id=?", (second,)).fetchone()[0] == "invited"


def _setup(conn, t0, starts_in_min=120, people=3):
    """Property 1, `people` applicants with calendar access (ids 1..), one slot (id 1).
    Applicant 1 holds the slot; the others are free to join the waiting list."""
    conn.execute("INSERT INTO properties (id,title,address,city,rental_type,rent_eur,required_document,created_at) "
                 "VALUES (1,'P','A','C','residential',900,'Payslip',?)", (t0.isoformat(),))
    for i in range(1, people + 1):
        conn.execute("INSERT INTO applications (id,property_id,token,name,source,status,calendar_access,created_at) "
                     "VALUES (?,1,?,?,'link','invited',1,?)", (i, f"t{i}", f"N{i}", t0.isoformat()))
    start = (t0 + timedelta(minutes=starts_in_min)).isoformat()
    conn.execute("INSERT INTO slots (id,property_id,starts_at) VALUES (1,1,?)", (start,))
    scheduling.book(conn, 1, 1, t0)
    return start


def _slot(conn):
    return conn.execute("SELECT * FROM slots WHERE id=1").fetchone()


def _notes(conn):
    return conn.execute("SELECT application_id FROM notifications WHERE application_id IS NOT NULL").fetchall()


def test_cancel_offers_to_first_in_line_only(conn, t0):
    _setup(conn, t0)
    scheduling.join_waitlist(conn, 2, 1, t0)
    scheduling.join_waitlist(conn, 3, 1, t0 + timedelta(minutes=1))
    scheduling.cancel_booking(conn, 1, "applicant", t0)
    slot = _slot(conn)
    assert slot["booked_application_id"] is None
    assert slot["offer_application_id"] == 2
    notes = _notes(conn)
    assert [n[0] for n in notes] == [2]


@pytest.mark.parametrize("starts_in, expected_min", [(120, 30), (10, 10)])
def test_offer_deadline_is_min_of_30_min_and_start(conn, t0, starts_in, expected_min):
    _setup(conn, t0, starts_in_min=starts_in)
    scheduling.join_waitlist(conn, 2, 1, t0)
    scheduling.cancel_booking(conn, 1, "applicant", t0)
    assert _slot(conn)["offer_expires_at"] == (t0 + timedelta(minutes=expected_min)).isoformat()


def test_decline_passes_on_and_last_decline_frees_slot(conn, t0):
    _setup(conn, t0)
    scheduling.join_waitlist(conn, 2, 1, t0)
    scheduling.join_waitlist(conn, 3, 1, t0 + timedelta(minutes=1))
    scheduling.cancel_booking(conn, 1, "applicant", t0)
    scheduling.decline_offer(conn, 2, 1, t0)
    assert _slot(conn)["offer_application_id"] == 3
    scheduling.decline_offer(conn, 3, 1, t0)
    slot = _slot(conn)
    assert slot["offer_application_id"] is None and slot["booked_application_id"] is None
    assert slot["offer_expires_at"] is None


def test_tick_expires_offer_after_31_minutes(conn, t0):
    _setup(conn, t0)
    scheduling.join_waitlist(conn, 2, 1, t0)
    scheduling.join_waitlist(conn, 3, 1, t0 + timedelta(minutes=1))
    scheduling.cancel_booking(conn, 1, "applicant", t0)
    assert scheduling.tick(conn, t0 + timedelta(minutes=29)) == 0
    later = t0 + timedelta(minutes=31)
    assert scheduling.tick(conn, later) == 1
    slot = _slot(conn)
    assert slot["offer_application_id"] == 3
    assert slot["offer_expires_at"] == (later + timedelta(minutes=30)).isoformat()
