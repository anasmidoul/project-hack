"""Unit B4 — scheduling: viewing slots, booking, waiting list and offer relay.

Contract: DESIGN.md section 7 (scheduling.py).

Rules:
- `book`: applicant has `calendar_access`; slot is in the future, has no booking and no offer;
  applicant has no other booking for this property. Otherwise `DomainError`. The check and the
  write happen in the caller's transaction, so two applicants can never hold one slot.
- `join_waitlist`: slot must be booked by someone else or held; once per slot.
- `cancel_booking`: clears the booking, sets the applicant back to `invited`, then runs the relay.
- Relay (one private function used by cancel, decline and tick): take the first person on the
  waitlist. If there is one, set `offer_application_id` and
  `offer_expires_at = min(now + 30 min, starts_at)`, and send ONE notification to that
  applicant and one to the landlord. If the waitlist is empty, the slot becomes free.
- `accept_offer`: only by the offered applicant before expiry. Books the slot, removes them from
  the waitlist, clears the offer. If they had another booking on this property, that booking is
  cancelled first (its own relay runs).
- `decline_offer` and expiry in `tick`: remove that person from the waitlist, clear the offer,
  run the relay again.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from datetime import datetime, timedelta

from housia import core

if TYPE_CHECKING:
    import sqlite3
    from datetime import datetime


def create_slot(conn: sqlite3.Connection, property_id: int, starts_at: datetime,
                duration_min: int, now: datetime) -> int:
    """Create a viewing slot and return its id. starts_at must be in the future."""
    from housia.services.properties import get_property

    get_property(conn, property_id)
    if starts_at.replace(microsecond=0) <= now.replace(microsecond=0):
        raise core.DomainError("A viewing must be scheduled in the future.")
    if not isinstance(duration_min, int) or duration_min < 1 or duration_min > 480:
        raise core.DomainError("Viewing duration must be between 1 and 480 minutes.")
    cursor = conn.execute(
        "INSERT INTO slots (property_id,starts_at,duration_min) VALUES (?,?,?)",
        (property_id, starts_at.replace(microsecond=0).isoformat(), duration_min),
    )
    return cursor.lastrowid


def delete_slot(conn: sqlite3.Connection, slot_id: int) -> None:
    """Delete a slot, only if it has no booking, offer or waitlist."""
    slot = _get_slot(conn, slot_id)
    waiting = conn.execute("SELECT 1 FROM waitlist WHERE slot_id=? LIMIT 1", (slot_id,)).fetchone()
    if slot["booked_application_id"] is not None or slot["offer_application_id"] is not None or waiting:
        raise core.DomainError("A viewing with a booking, offer or waiting list cannot be deleted.")
    conn.execute("DELETE FROM slots WHERE id=?", (slot_id,))


def list_slots(conn: sqlite3.Connection, property_id: int) -> list[dict]:
    """Return the slots of a property for the landlord.

    Each: id, starts_at, duration_min, attendance, booked (Row|None),
    offer ({application: Row, expires_at}|None), waitlist (list[Row] of applications, in order).
    """
    from housia.services.properties import get_property

    get_property(conn, property_id)
    result = []
    rows = conn.execute("SELECT * FROM slots WHERE property_id=? ORDER BY starts_at,id", (property_id,)).fetchall()
    for slot in rows:
        booked = _application(conn, slot["booked_application_id"]) if slot["booked_application_id"] else None
        offer_app = _application(conn, slot["offer_application_id"]) if slot["offer_application_id"] else None
        waitlist = conn.execute(
            "SELECT a.* FROM waitlist w JOIN applications a ON a.id=w.application_id "
            "WHERE w.slot_id=? ORDER BY w.joined_at,w.id", (slot["id"],)
        ).fetchall()
        result.append({**dict(slot), "booked": booked,
                       "offer": ({"application": offer_app, "expires_at": slot["offer_expires_at"]}
                                 if offer_app else None),
                       "waitlist": waitlist})
    return result


def slots_for_applicant(conn: sqlite3.Connection, application_id: int,
                        now: datetime) -> list[dict]:
    """Return the slots as one applicant sees them.

    Each: id, starts_at, duration_min, state, offer_expires_at, waitlist_position.
    state: 'free' | 'mine' | 'taken' | 'waiting' | 'offered_to_me' | 'held' (offered to someone else)
    """
    applicant = _application(conn, application_id)
    rows = conn.execute("SELECT * FROM slots WHERE property_id=? ORDER BY starts_at,id",
                        (applicant["property_id"],)).fetchall()
    output = []
    for slot in rows:
        wait = conn.execute("SELECT id,joined_at FROM waitlist WHERE slot_id=? AND application_id=?",
                            (slot["id"], application_id)).fetchone()
        position = None
        if wait:
            position = conn.execute(
                "SELECT COUNT(*) FROM waitlist WHERE slot_id=? AND (joined_at < ? OR (joined_at=? AND id<=?))",
                (slot["id"], wait["joined_at"], wait["joined_at"], wait["id"]),
            ).fetchone()[0]
        if slot["booked_application_id"] == application_id:
            state = "mine"
        elif slot["offer_application_id"] == application_id:
            state = "offered_to_me"
        elif wait:
            state = "waiting"
        elif slot["offer_application_id"] is not None:
            state = "held"
        elif slot["booked_application_id"] is None:
            state = "free"
        else:
            state = "taken"
        output.append({"id": slot["id"], "starts_at": slot["starts_at"],
                       "duration_min": slot["duration_min"], "state": state,
                       "offer_expires_at": slot["offer_expires_at"], "waitlist_position": position})
    return output


def book(conn: sqlite3.Connection, application_id: int, slot_id: int, now: datetime) -> None:
    """Book a slot.

    Applicant has calendar_access; slot is in the future, has no booking and no offer;
    applicant has no other booking for this property. Otherwise DomainError. The check and the
    write happen in the caller's transaction, so two applicants can never hold one slot.
    """
    app = _application(conn, application_id)
    slot = _get_slot(conn, slot_id)
    if not app["calendar_access"]:
        raise core.DomainError("Calendar access is required to book a viewing.")
    if app["property_id"] != slot["property_id"]:
        raise core.DomainError("This viewing belongs to another property.")
    if slot["starts_at"] <= now.replace(microsecond=0).isoformat():
        raise core.DomainError("This viewing has already started.")
    if slot["booked_application_id"] is not None or slot["offer_application_id"] is not None:
        raise core.DomainError("This viewing is no longer available.")
    other = conn.execute("SELECT 1 FROM slots WHERE property_id=? AND booked_application_id=?",
                         (slot["property_id"], application_id)).fetchone()
    if other:
        raise core.DomainError("You already have a viewing booked for this property.")
    conn.execute("UPDATE slots SET booked_application_id=? WHERE id=?", (application_id, slot_id))
    core.set_status(conn, application_id, "booked")


def cancel_booking(conn: sqlite3.Connection, slot_id: int, by: str, now: datetime) -> None:
    """Cancel a booking. by: 'applicant' | 'landlord'.

    Clears the booking, sets the applicant back to 'invited', then runs the relay.
    """
    if by not in {"applicant", "landlord"}:
        raise core.DomainError("Unknown cancellation source.")
    slot = _get_slot(conn, slot_id)
    application_id = slot["booked_application_id"]
    if application_id is None:
        raise core.DomainError("This viewing has no booking to cancel.")
    conn.execute("UPDATE slots SET booked_application_id=NULL, attendance=NULL WHERE id=?", (slot_id,))
    core.set_status(conn, application_id, "invited")
    _relay(conn, slot_id, now)


def join_waitlist(conn: sqlite3.Connection, application_id: int, slot_id: int,
                  now: datetime) -> None:
    """Join the waiting list. The slot must be booked by someone else or held; once per slot."""
    app = _application(conn, application_id)
    slot = _get_slot(conn, slot_id)
    if app["property_id"] != slot["property_id"] or not app["calendar_access"]:
        raise core.DomainError("Calendar access for this property is required.")
    if slot["starts_at"] <= now.replace(microsecond=0).isoformat():
        raise core.DomainError("This viewing has already started.")
    if slot["booked_application_id"] in (None, application_id) and slot["offer_application_id"] in (None, application_id):
        raise core.DomainError("This viewing does not have a waiting list.")
    if conn.execute("SELECT 1 FROM waitlist WHERE slot_id=? AND application_id=?", (slot_id, application_id)).fetchone():
        raise core.DomainError("You are already on this waiting list.")
    conn.execute("INSERT INTO waitlist (slot_id,application_id,joined_at) VALUES (?,?,?)",
                 (slot_id, application_id, now.replace(microsecond=0).isoformat()))


def leave_waitlist(conn: sqlite3.Connection, application_id: int, slot_id: int,
                   now: datetime) -> None:
    """Leave the waiting list of a slot."""
    slot = _get_slot(conn, slot_id)
    row = conn.execute("SELECT id FROM waitlist WHERE slot_id=? AND application_id=?", (slot_id, application_id)).fetchone()
    if row is None:
        raise core.DomainError("You are not on this waiting list.")
    if slot["offer_application_id"] == application_id:
        conn.execute("DELETE FROM waitlist WHERE id=?", (row["id"],))
        conn.execute("UPDATE slots SET offer_application_id=NULL,offer_expires_at=NULL WHERE id=?", (slot_id,))
        _relay(conn, slot_id, now)
    else:
        conn.execute("DELETE FROM waitlist WHERE id=?", (row["id"],))


def accept_offer(conn: sqlite3.Connection, application_id: int, slot_id: int,
                 now: datetime) -> None:
    """Accept an offer: only by the offered applicant before expiry.

    Books the slot, removes them from the waitlist, clears the offer. If they had another
    booking on this property, that booking is cancelled first (its own relay runs).
    """
    slot = _get_slot(conn, slot_id)
    if slot["offer_application_id"] != application_id:
        raise core.DomainError("There is no viewing offer for this applicant.")
    if not slot["offer_expires_at"] or slot["offer_expires_at"] <= now.replace(microsecond=0).isoformat():
        raise core.DomainError("This viewing offer has expired.")
    other = conn.execute("SELECT id FROM slots WHERE property_id=? AND booked_application_id=? AND id<>?",
                         (slot["property_id"], application_id, slot_id)).fetchone()
    if other:
        cancel_booking(conn, other["id"], "applicant", now)
    conn.execute("DELETE FROM waitlist WHERE slot_id=? AND application_id=?", (slot_id, application_id))
    conn.execute("UPDATE slots SET booked_application_id=?,offer_application_id=NULL,offer_expires_at=NULL WHERE id=?",
                 (application_id, slot_id))
    core.set_status(conn, application_id, "booked")


def decline_offer(conn: sqlite3.Connection, application_id: int, slot_id: int,
                  now: datetime) -> None:
    """Decline an offer: remove that person from the waitlist, clear the offer, run the relay again."""
    slot = _get_slot(conn, slot_id)
    if slot["offer_application_id"] != application_id:
        raise core.DomainError("There is no viewing offer for this applicant.")
    conn.execute("DELETE FROM waitlist WHERE slot_id=? AND application_id=?", (slot_id, application_id))
    conn.execute("UPDATE slots SET offer_application_id=NULL,offer_expires_at=NULL WHERE id=?", (slot_id,))
    _relay(conn, slot_id, now)


def tick(conn: sqlite3.Connection, now: datetime) -> int:
    """Expire overdue offers and return how many."""
    expired = conn.execute("SELECT id,offer_application_id FROM slots WHERE offer_application_id IS NOT NULL AND offer_expires_at<=?",
                           (now.replace(microsecond=0).isoformat(),)).fetchall()
    for row in expired:
        conn.execute("DELETE FROM waitlist WHERE slot_id=? AND application_id=?",
                     (row["id"], row["offer_application_id"]))
        conn.execute("UPDATE slots SET offer_application_id=NULL,offer_expires_at=NULL WHERE id=?", (row["id"],))
        _relay(conn, row["id"], now)
    return len(expired)


def _application(conn, application_id):
    row = conn.execute("SELECT * FROM applications WHERE id=?", (application_id,)).fetchone()
    if row is None:
        raise core.DomainError("Application not found.")
    return row


def _get_slot(conn, slot_id):
    row = conn.execute("SELECT * FROM slots WHERE id=?", (slot_id,)).fetchone()
    if row is None:
        raise core.DomainError("Viewing slot not found.")
    return row


def _relay(conn, slot_id, now):
    slot = _get_slot(conn, slot_id)
    if slot["booked_application_id"] is not None:
        return
    next_app = conn.execute(
        "SELECT w.id,w.application_id,a.name FROM waitlist w JOIN applications a ON a.id=w.application_id "
        "WHERE w.slot_id=? ORDER BY w.joined_at,w.id LIMIT 1", (slot_id,)
    ).fetchone()
    if next_app is None:
        conn.execute("UPDATE slots SET offer_application_id=NULL,offer_expires_at=NULL WHERE id=?", (slot_id,))
        return
    start = datetime.fromisoformat(slot["starts_at"])
    deadline = min(now.replace(microsecond=0) + timedelta(minutes=30), start)
    conn.execute("UPDATE slots SET offer_application_id=?,offer_expires_at=? WHERE id=?",
                 (next_app["application_id"], deadline.isoformat(), slot_id))
    property_id = slot["property_id"]
    core.notify(conn, property_id=property_id, application_id=next_app["application_id"],
                title="A viewing slot is available", body=f"A viewing slot is available at {slot['starts_at']}. Accept before {deadline.isoformat()}.", now=now)
    core.notify(conn, property_id=property_id, application_id=None,
                title="Viewing offer sent", body=f"An offer was sent to {next_app['name']}.", now=now)
