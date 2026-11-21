import pytest

from housia import core, seed
from housia.services import contracts, postviewing


def test_finalist_must_have_attended(conn, t0):
    seed.run(conn, t0)
    applicant = conn.execute("SELECT id FROM applications WHERE name='Hugo Vidal'").fetchone()[0]
    with pytest.raises(core.DomainError):
        postviewing.select_finalist(conn, 2, applicant, t0)


def test_attendance_finalist_and_signed_contract_close_other_applicants(conn, t0):
    seed.run(conn, t0)
    slot = conn.execute("SELECT id FROM slots WHERE property_id=2").fetchone()[0]
    applicant = conn.execute("SELECT id FROM applications WHERE name='Gabi Soler'").fetchone()[0]
    postviewing.set_attendance(conn, slot, "attended", t0)
    assert postviewing.attended_applications(conn, 2)[0]["id"] == applicant
    postviewing.select_finalist(conn, 2, applicant, t0)
    contracts.set_contract_status(conn, 2, "pending", t0)
    contracts.set_contract_status(conn, 2, "sent", t0)
    with pytest.raises(core.DomainError):
        contracts.attach_signed(conn, 2, "missing.pdf", t0)
    filename = contracts.demo_contract_files()[0]
    contracts.attach_signed(conn, 2, filename, t0)
    assert tuple(conn.execute("SELECT contract_status,signed_contract_file FROM properties WHERE id=2").fetchone()) == ("signed", filename)
    assert conn.execute("SELECT status FROM applications WHERE id=?", (applicant,)).fetchone()[0] == "completed"
    assert conn.execute("SELECT COUNT(*) FROM applications WHERE property_id=2 AND status='closed'").fetchone()[0] == 6
    assert conn.execute("SELECT COUNT(*) FROM notifications WHERE property_id=2 AND application_id IS NOT NULL").fetchone()[0] >= 6
