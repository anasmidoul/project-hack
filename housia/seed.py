"""Unit B7 — seed data: demo content loaded by db.reset_db().

Contract: DESIGN.md section 10.

seed.run(conn, now) must make both demo moments work straight after a reset. Dates are
relative to `now`.

- Property 1: residential, Madrid, eval_mode='assisted', reply_mode='automatic',
  invite_limit=3, with facts filled in. Six applications: one new, one docs_requested,
  one docs_uploaded, three docs_approved with different availability, two of them tied on
  score so the tie-break shows. Three free slots.
- Property 2: temporary, Valencia, eval_mode='automatic', reply_mode='assisted',
  invite_limit=5. Three applicants already invited: X has a slot tomorrow, Y then Z are on
  its waiting list. Four more docs_approved, so an automatic run invites two and leaves two.
- Mock portal: three unanswered threads for property 1: a first contact, a question the
  facts answer, and a question they do not.
- Names are fictional, emails end in @example.com, phones look like 600 000 001.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from datetime import timedelta

if TYPE_CHECKING:
    import sqlite3
    from datetime import datetime


def run(conn: sqlite3.Connection, now: datetime) -> None:
    """Insert the two-property demo workflow and mock portal conversations."""
    stamp = now.replace(microsecond=0).isoformat()
    properties = [
        ("Sunny room near Retiro", "Calle de Ibiza 14", "Madrid", "residential", 950,
         "Bright furnished room in a shared flat.",
         "Bills included. The flat is 8 minutes from Retiro station. No pets. Available from December 1.",
         "Latest payslip", "assisted", 3, "automatic", "demo-madrid"),
        ("Temporary stay in Ruzafa", "Carrer de Cadis 22", "Valencia", "temporary", 1100,
         "Furnished temporary apartment in Ruzafa.",
         "Two bedrooms. Minimum stay is 3 months. Bills are not included.",
         "Proof of enrolment", "automatic", 5, "assisted", "demo-valencia"),
    ]
    for values in properties:
        conn.execute(
            "INSERT INTO properties (title,address,city,rental_type,rent_eur,description,facts,"
            "required_document,eval_mode,invite_limit,reply_mode,listing_ref,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (*values, stamp),
        )

    records = [
        # Property 1 applications: new, requested, uploaded, then ranked candidates.
        (1, "Alex Rivera", "alex@example.com", "600 000 001", "link", "Quiet tenant", "morning", "new", None, -6),
        (1, "Bea Martín", "bea@example.com", "600 000 002", "idealista", "Near work", "afternoon", "docs_requested", None, -5),
        (1, "Cris Gómez", "cris@example.com", "600 000 003", "mock", "No smoking", "weekend", "docs_uploaded", "enrolment-demo.pdf", -4),
        (1, "Dani López", "dani@example.com", "600 000 004", "link", "Flexible", "morning,afternoon", "docs_approved", "payslip-demo.pdf", -3),
        (1, "Eva Torres", "eva@example.com", "600 000 005", "fotocasa", "Quiet area", "morning,afternoon", "docs_approved", "payslip-demo.pdf", -2),
        (1, "Fran Ruiz", "fran@example.com", "600 000 006", "whatsapp", "Near transit", "weekend", "docs_approved", "payslip-demo.pdf", -1),
        # Property 2: three invited applicants and four automatic-evaluation candidates.
        (2, "Gabi Soler", "gabi@example.com", "600 000 007", "link", "Three months", "morning", "booked", None, -6),
        (2, "Hugo Vidal", "hugo@example.com", "600 000 008", "link", "Three months", "afternoon", "invited", None, -5),
        (2, "Inés Ferrer", "ines@example.com", "600 000 009", "link", "Three months", "weekend", "invited", None, -4),
        (2, "Júlia Serra", "julia@example.com", "600 000 010", "link", "Three months", "morning", "docs_approved", "enrolment-demo.pdf", -3),
        (2, "Kai Costa", "kai@example.com", "600 000 011", "link", "Three months", "afternoon", "docs_approved", "enrolment-demo.pdf", -2),
        (2, "Luz Ferrer", "luz@example.com", "600 000 012", "link", "Three months", "weekend", "docs_approved", "enrolment-demo.pdf", -1),
        (2, "Mia Roca", "mia@example.com", "600 000 013", "link", "Three months", "morning,weekend", "docs_approved", "enrolment-demo.pdf", 0),
    ]
    app_ids = {}
    for prop_id, name, email, phone, source, preferences, availability, status, doc_file, offset in records:
        created = (now + timedelta(minutes=offset)).replace(microsecond=0).isoformat()
        cursor = conn.execute(
            "INSERT INTO applications (property_id,token,name,email,phone,source,preferences,"
            "availability,status,doc_file,calendar_access,invited_by,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (prop_id, f"demo-{prop_id}-{len(app_ids)+1:02d}", name, email, phone, source,
             preferences, availability, status, doc_file,
             int(status in {"invited", "booked"}), "landlord" if status in {"invited", "booked"} else None,
             created),
        )
        app_ids[name] = cursor.lastrowid

    # Three free slots with varied time bands for the assisted evaluation.
    free_slots = [now + timedelta(days=1), now + timedelta(days=2, hours=6), now + timedelta(days=5)]
    for starts in free_slots:
        conn.execute("INSERT INTO slots (property_id,starts_at,duration_min) VALUES (1,?,30)",
                     (starts.replace(microsecond=0).isoformat(),))
    tomorrow = (now + timedelta(days=1)).replace(microsecond=0)
    slot = conn.execute(
        "INSERT INTO slots (property_id,starts_at,duration_min,booked_application_id) "
        "VALUES (2,?,30,?) RETURNING id",
        (tomorrow.isoformat(), app_ids["Gabi Soler"]),
    ).fetchone()
    conn.execute("INSERT INTO waitlist (slot_id,application_id,joined_at) VALUES (?,?,?)",
                 (slot["id"], app_ids["Hugo Vidal"], stamp))
    conn.execute("INSERT INTO waitlist (slot_id,application_id,joined_at) VALUES (?,?,?)",
                 (slot["id"], app_ids["Inés Ferrer"], (now + timedelta(seconds=1)).isoformat()))
    for name in ("Gabi Soler", "Hugo Vidal", "Inés Ferrer"):
        conn.execute("UPDATE applications SET calendar_access=1, invited_by='landlord' WHERE id=?",
                     (app_ids[name],))

    # Mock portal threads are unanswered so the worker can demonstrate its first-contact path.
    threads = [
        ("Nora Demo", "Hi, is the room still available?", "demo-madrid"),
        ("Pablo Demo", "Are bills included?", "demo-madrid"),
        ("Sara Demo", "Can I bring a large dog?", "demo-madrid"),
    ]
    for index, (contact, body, listing_ref) in enumerate(threads):
        cursor = conn.execute(
            "INSERT INTO mock_threads (contact_name,listing_ref,created_at) VALUES (?,?,?)",
            (contact, listing_ref, (now + timedelta(seconds=index)).replace(microsecond=0).isoformat()),
        )
        conn.execute(
            "INSERT INTO mock_messages (thread_id,sender,body,created_at,fetched) VALUES (?,?,?,?,0)",
            (cursor.lastrowid, "candidate", body, stamp),
        )
