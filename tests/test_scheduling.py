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
