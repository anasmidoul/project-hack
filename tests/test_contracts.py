"""Unit B5 tests: finalist selection and the signed contract."""
import pytest

from housia import core
from housia.services import contracts, postviewing


def _setup(conn, t0):
    """Property 1 with applicants 1 (attended), 2 (invited) and 3 (new)."""
    conn.execute("INSERT INTO properties (id,title,address,city,rental_type,rent_eur,required_document,created_at) "
                 "VALUES (1,'P','A','C','residential',900,'Payslip',?)", (t0.isoformat(),))
    for i, status in ((1, "booked"), (2, "invited"), (3, "new")):
        conn.execute("INSERT INTO applications (id,property_id,token,name,source,status,created_at) "
                     "VALUES (?,1,?,?,'link',?,?)", (i, f"t{i}", f"N{i}", status, t0.isoformat()))
    conn.execute("INSERT INTO slots (id,property_id,starts_at,booked_application_id) VALUES (1,1,?,1)",
                 (t0.isoformat(),))


def _status(conn, app_id):
    return conn.execute("SELECT status FROM applications WHERE id=?", (app_id,)).fetchone()[0]


def test_select_finalist_needs_attendance(conn, t0):
    _setup(conn, t0)
    with pytest.raises(core.DomainError):
        postviewing.select_finalist(conn, 1, 1, t0)  # booked, not yet attended
    postviewing.set_attendance(conn, 1, "attended", t0)
    postviewing.select_finalist(conn, 1, 1, t0)
    assert _status(conn, 1) == "finalist"


def test_signing_needs_sent_and_a_contract_file(conn, t0):
    _setup(conn, t0)
    postviewing.set_attendance(conn, 1, "attended", t0)
    postviewing.select_finalist(conn, 1, 1, t0)
    name = contracts.demo_contract_files()[0]
    contracts.set_contract_status(conn, 1, "pending", t0)
    with pytest.raises(core.DomainError):
        contracts.attach_signed(conn, 1, name, t0)  # not sent yet
    contracts.set_contract_status(conn, 1, "sent", t0)
    with pytest.raises(core.DomainError):
        contracts.attach_signed(conn, 1, "nope.pdf", t0)
    contracts.attach_signed(conn, 1, name, t0)
    row = conn.execute("SELECT contract_status,signed_contract_file FROM properties WHERE id=1").fetchone()
    assert tuple(row) == ("signed", name)


def test_signing_completes_finalist_and_closes_others(conn, t0):
    _setup(conn, t0)
    postviewing.set_attendance(conn, 1, "attended", t0)
    postviewing.select_finalist(conn, 1, 1, t0)
    contracts.set_contract_status(conn, 1, "sent", t0)
    contracts.attach_signed(conn, 1, contracts.demo_contract_files()[0], t0)
    assert _status(conn, 1) == "completed"
    assert _status(conn, 2) == "closed"
    assert _status(conn, 3) == "closed"
