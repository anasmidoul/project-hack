from datetime import timedelta

from housia import seed
from housia.services import scheduling


def test_seed_waitlist_demo_relay_offers_to_y_then_z(conn, t0):
    seed.run(conn, t0)
    slot = conn.execute("SELECT id FROM slots WHERE property_id=2").fetchone()[0]
    scheduling.cancel_booking(conn, slot, "landlord", t0)
    assert conn.execute("SELECT name FROM applications WHERE id=(SELECT offer_application_id FROM slots WHERE id=?)",
                        (slot,)).fetchone()[0] == "Hugo Vidal"
    applicant_notices = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE application_id=(SELECT offer_application_id FROM slots WHERE id=?)",
        (slot,),
    ).fetchone()[0]
    assert applicant_notices == 1
    assert scheduling.tick(conn, t0 + timedelta(minutes=31)) == 1
    assert conn.execute("SELECT name FROM applications WHERE id=(SELECT offer_application_id FROM slots WHERE id=?)",
                        (slot,)).fetchone()[0] == "Inés Ferrer"
