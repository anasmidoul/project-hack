"""Route unit A1: mock_inbox blueprint.

Contract: DESIGN.md section 9.
"""

from flask import Blueprint, abort, flash, redirect, render_template, request

from housia import core, db

bp = Blueprint("mock_inbox", __name__)


def _threads(conn):
    rows = conn.execute(
        "SELECT t.*, "
        " (SELECT body FROM mock_messages m WHERE m.thread_id = t.id ORDER BY m.id DESC LIMIT 1) AS last_message, "
        " (SELECT sender FROM mock_messages m WHERE m.thread_id = t.id ORDER BY m.id DESC LIMIT 1) AS last_sender, "
        " COALESCE((SELECT MAX(created_at) FROM mock_messages m WHERE m.thread_id = t.id), t.created_at) AS last_at "
        "FROM mock_threads t ORDER BY last_at DESC, t.id DESC"
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["unanswered"] = d.pop("last_sender") == "candidate"
        result.append(d)
    return result


def _iso(conn) -> str:
    return core.now(conn).replace(microsecond=0).isoformat()


@bp.get("/mock/inbox")
def inbox():
    with db.tx() as conn:
        threads = _threads(conn)
    return render_template("mock_inbox.html", threads=threads)


@bp.get("/mock/inbox/<int:thread_id>")
def thread(thread_id):
    with db.tx() as conn:
        row = conn.execute("SELECT * FROM mock_threads WHERE id = ?", (thread_id,)).fetchone()
        if row is None:
            abort(404)
        messages = conn.execute(
            "SELECT * FROM mock_messages WHERE thread_id = ? ORDER BY created_at, id",
            (thread_id,),
        ).fetchall()
    return render_template("mock_thread.html", thread=row, messages=messages)


@bp.post("/mock/inbox/<int:thread_id>/send")
def thread_send(thread_id):
    body = request.form.get("body", "").strip()
    try:
        if not body:
            raise core.DomainError("The message is empty.")
        with db.tx() as conn:
            if conn.execute("SELECT 1 FROM mock_threads WHERE id = ?", (thread_id,)).fetchone() is None:
                abort(404)
            conn.execute(
                "INSERT INTO mock_messages (thread_id, sender, body, created_at) "
                "VALUES (?, 'landlord', ?, ?)",
                (thread_id, body, _iso(conn)),
            )
        flash("Message sent.", "ok")
    except core.DomainError as e:
        flash(str(e), "error")
    return redirect(f"/mock/inbox/{thread_id}")


@bp.get("/mock/candidate")
def candidate():
    with db.tx() as conn:
        threads = _threads(conn)
    return render_template("mock_candidate.html", threads=threads)


@bp.post("/mock/candidate/send")
def candidate_send():
    body = request.form.get("body", "").strip()
    thread_raw = request.form.get("thread_id", "").strip()
    contact_name = request.form.get("contact_name", "").strip()
    try:
        if not body:
            raise core.DomainError("The message is empty.")
        with db.tx() as conn:
            now = _iso(conn)
            if thread_raw:
                try:
                    thread_id = int(thread_raw)
                except ValueError:
                    raise core.DomainError("Unknown conversation.")
                if conn.execute("SELECT 1 FROM mock_threads WHERE id = ?", (thread_id,)).fetchone() is None:
                    raise core.DomainError("Unknown conversation.")
            else:
                prop = conn.execute("SELECT listing_ref FROM properties WHERE id = 1").fetchone()
                cur = conn.execute(
                    "INSERT INTO mock_threads (contact_name, listing_ref, created_at) VALUES (?, ?, ?)",
                    (contact_name or "Anonymous", prop["listing_ref"] if prop else None, now),
                )
                thread_id = cur.lastrowid
            conn.execute(
                "INSERT INTO mock_messages (thread_id, sender, body, created_at) "
                "VALUES (?, 'candidate', ?, ?)",
                (thread_id, body, now),
            )
        flash("Message sent.", "ok")
    except core.DomainError as e:
        flash(str(e), "error")
    return redirect("/mock/candidate")
