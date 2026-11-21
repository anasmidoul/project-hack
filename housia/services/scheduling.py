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

if TYPE_CHECKING:
    import sqlite3
    from datetime import datetime


def create_slot(conn: sqlite3.Connection, property_id: int, starts_at: datetime,
                duration_min: int, now: datetime) -> int:
    """Create a viewing slot and return its id. starts_at must be in the future."""
    raise NotImplementedError("B4: scheduling.create_slot")


def delete_slot(conn: sqlite3.Connection, slot_id: int) -> None:
    """Delete a slot, only if it has no booking, offer or waitlist."""
    raise NotImplementedError("B4: scheduling.delete_slot")


def list_slots(conn: sqlite3.Connection, property_id: int) -> list[dict]:
    """Return the slots of a property for the landlord.

    Each: id, starts_at, duration_min, attendance, booked (Row|None),
    offer ({application: Row, expires_at}|None), waitlist (list[Row] of applications, in order).
    """
    raise NotImplementedError("B4: scheduling.list_slots")


def slots_for_applicant(conn: sqlite3.Connection, application_id: int,
                        now: datetime) -> list[dict]:
    """Return the slots as one applicant sees them.

    Each: id, starts_at, duration_min, state, offer_expires_at, waitlist_position.
    state: 'free' | 'mine' | 'taken' | 'waiting' | 'offered_to_me' | 'held' (offered to someone else)
    """
    raise NotImplementedError("B4: scheduling.slots_for_applicant")


def book(conn: sqlite3.Connection, application_id: int, slot_id: int, now: datetime) -> None:
    """Book a slot.

    Applicant has calendar_access; slot is in the future, has no booking and no offer;
    applicant has no other booking for this property. Otherwise DomainError. The check and the
    write happen in the caller's transaction, so two applicants can never hold one slot.
    """
    raise NotImplementedError("B4: scheduling.book")


def cancel_booking(conn: sqlite3.Connection, slot_id: int, by: str, now: datetime) -> None:
    """Cancel a booking. by: 'applicant' | 'landlord'.

    Clears the booking, sets the applicant back to 'invited', then runs the relay.
    """
    raise NotImplementedError("B4: scheduling.cancel_booking")


def join_waitlist(conn: sqlite3.Connection, application_id: int, slot_id: int,
                  now: datetime) -> None:
    """Join the waiting list. The slot must be booked by someone else or held; once per slot."""
    raise NotImplementedError("B4: scheduling.join_waitlist")


def leave_waitlist(conn: sqlite3.Connection, application_id: int, slot_id: int,
                   now: datetime) -> None:
    """Leave the waiting list of a slot."""
    raise NotImplementedError("B4: scheduling.leave_waitlist")


def accept_offer(conn: sqlite3.Connection, application_id: int, slot_id: int,
                 now: datetime) -> None:
    """Accept an offer: only by the offered applicant before expiry.

    Books the slot, removes them from the waitlist, clears the offer. If they had another
    booking on this property, that booking is cancelled first (its own relay runs).
    """
    raise NotImplementedError("B4: scheduling.accept_offer")


def decline_offer(conn: sqlite3.Connection, application_id: int, slot_id: int,
                  now: datetime) -> None:
    """Decline an offer: remove that person from the waitlist, clear the offer, run the relay again."""
    raise NotImplementedError("B4: scheduling.decline_offer")


def tick(conn: sqlite3.Connection, now: datetime) -> int:
    """Expire overdue offers and return how many.

    For each expired offer: remove that person from the waitlist, clear the offer, run the
    relay again. Harmless stub: returns 0 until B4 implements it.
    """
    return 0
