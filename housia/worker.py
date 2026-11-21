"""Unit A3 — worker: separate process that moves messages channel -> services -> channel.

Contract: DESIGN.md section 8 (A3 — worker). Run with `python -m housia.worker` or `--once`.

Rules:
- No transaction is open while a model or the browser is working.
- If the worker stops between steps, the next loop picks the message up again from
  `unanswered`. The `one_reply_per_incoming` index stops a second reply.
- The landlord approving a draft only sets it to `approved`. The worker sends it on its next
  loop. The web app never sends.
- Loop interval: `config.WORKER_INTERVAL_SEC`.
"""
from __future__ import annotations

import argparse
import time
import traceback
from contextlib import closing
from typing import TYPE_CHECKING

from housia import config, core, db
from housia.services import applications, conversations, reply_engine

if TYPE_CHECKING:
    from housia.channels.base import Channel

# Messages that were really shown to the contact, or are about to be. Drafts, discarded and
# failed replies are not part of the history the reply engine sees.
_HISTORY_STATUSES = ("received", "approved", "sent")


def _log(text: str) -> None:
    print(f"[worker] {text}", flush=True)


def _property_for(conn, listing_ref: str | None) -> int:
    if listing_ref:
        row = conn.execute("SELECT id FROM properties WHERE listing_ref = ? ORDER BY id LIMIT 1",
                           (listing_ref,)).fetchone()
        if row is not None:
            return row["id"]
    return config.DEFAULT_PROPERTY_ID


def _ensure_application(conversation_id: int, channel_name: str) -> str:
    """Give the conversation an application if it has none. Returns the application token."""
    with db.tx() as conn:
        conv = conversations.get_conversation(conn, conversation_id)
        app_id = conv["application_id"]
        if app_id is None:
            app_id = applications.create_application(
                conn, conv["property_id"], {"name": conv["contact_name"] or "Portal contact"},
                channel_name, core.now(conn))
            conversations.link_application(conn, conversation_id, app_id)
        row = conn.execute("SELECT token FROM applications WHERE id = ?", (app_id,)).fetchone()
        if row is None:
            raise core.DomainError("Application not found.")
        return row["token"]


def _record(channel: Channel, counts: dict) -> None:
    for msg in channel.fetch_new_messages():
        try:
            with db.tx() as conn:
                property_id = _property_for(conn, msg.listing_ref)
                message_id = conversations.record_incoming(
                    conn, channel.name, msg, property_id, core.now(conn))
                conv_id = conn.execute(
                    "SELECT id FROM conversations WHERE channel = ? AND external_id = ?",
                    (channel.name, msg.external_conversation_id)).fetchone()["id"]
            if message_id is not None:
                counts["recorded"] += 1
            # Separate transaction: if the application cannot be created, the message is still
            # kept and step 2 tries again.
            _ensure_application(conv_id, channel.name)
        except Exception:
            counts["errors"] += 1
            _log("could not record a message:\n" + traceback.format_exc())


def _reply(channel: Channel, counts: dict) -> None:
    with closing(db.get_conn()) as conn:
        pending = conversations.unanswered(conn, channel.name)
    for m in pending:
        try:
            token = _ensure_application(m["conversation_id"], channel.name)
            with closing(db.get_conn()) as conn:
                prop = conn.execute("SELECT * FROM properties WHERE id = ?",
                                    (m["property_id"],)).fetchone()
                if prop is None:
                    raise core.DomainError(f"Property {m['property_id']} not found.")
                prop = dict(prop)
                history = [
                    {"direction": h["direction"], "body": h["body"]}
                    for h in conversations.get_thread(conn, m["conversation_id"])
                    # Everything said so far, including replies to earlier messages, but not
                    # this message or incoming messages that came after it.
                    if h["status"] in _HISTORY_STATUSES
                    and not (h["direction"] == "in" and h["id"] >= m["id"])
                ]
            # No connection or transaction open while the reply engine works.
            decision = reply_engine.generate_reply(
                prop, history, m["body"], m["contact_name"], core.applicant_url(token))
            with db.tx() as conn:
                now = core.now(conn)
                if decision.needs_landlord:
                    conversations.save_outgoing(conn, m["conversation_id"], decision.text,
                                                "draft", m["id"], decision.reason or None, now)
                    conversations.set_conversation_status(conn, m["conversation_id"],
                                                          "needs_landlord")
                    core.notify(conn, property_id=prop["id"], application_id=None,
                                title=f"{m['contact_name'] or 'A contact'} needs your answer",
                                body=decision.reason or "", now=now)
                    counts["drafted"] += 1
                elif prop["reply_mode"] == "assisted":
                    conversations.save_outgoing(conn, m["conversation_id"], decision.text,
                                                "draft", m["id"], None, now)
                    core.notify(conn, property_id=prop["id"], application_id=None,
                                title=f"Reply ready for {m['contact_name'] or 'a contact'}",
                                body="A draft reply is waiting for your approval.", now=now)
                    counts["drafted"] += 1
                else:
                    conversations.save_outgoing(conn, m["conversation_id"], decision.text,
                                                "approved", m["id"], None, now)
                    counts["approved"] += 1
        except Exception:
            counts["errors"] += 1
            _log(f"could not reply to message {m['id']}:\n" + traceback.format_exc())


def _send(channel: Channel, counts: dict) -> None:
    with closing(db.get_conn()) as conn:
        outgoing = conversations.pending_to_send(conn, channel.name)
    for out in outgoing:
        try:
            # No connection or transaction open while the channel works.
            channel.send_reply(out["external_id"], out["body"])
        except Exception as e:  # ChannelError or anything else: never resend automatically
            with db.tx() as conn:
                conversations.mark_failed(conn, out["id"], str(e) or type(e).__name__)
            counts["failed"] += 1
            _log(f"sending message {out['id']} failed: {e!r}")
            continue
        with db.tx() as conn:
            conversations.mark_sent(conn, out["id"], core.now(conn))
        counts["sent"] += 1


def run_once(channel: Channel) -> dict:
    """Run one worker loop on the given channel and return a summary dict.

    Keys: paused, recorded, drafted, approved, sent, failed, errors.
    """
    counts = {"paused": False, "recorded": 0, "drafted": 0, "approved": 0, "sent": 0,
              "failed": 0, "errors": 0}
    with closing(db.get_conn()) as conn:
        if core.get_setting(conn, "worker_paused", "0") == "1":
            counts["paused"] = True
            return counts
    _record(channel, counts)
    _reply(channel, counts)
    _send(channel, counts)
    return counts


def run_sandboxes() -> dict:
    """One worker loop, on the mock channel only, in every guest sandbox used in the last hour.

    Skipped entirely unless config.CHANNEL is 'mock'. A failure in one sandbox is logged and the
    others still run. Returns totals over all sandboxes plus 'sandboxes' (how many ran)."""
    from housia import sandbox
    from housia.channels.mock import MockChannel

    totals = {"sandboxes": 0, "recorded": 0, "drafted": 0, "approved": 0, "sent": 0,
              "failed": 0, "errors": 0}
    if config.CHANNEL != "mock":
        return totals
    for path in sandbox.recent():
        try:
            with db.using(path):
                counts = run_once(MockChannel())
        except Exception:
            totals["errors"] += 1
            _log("sandbox loop failed:\n" + traceback.format_exc())
            continue
        totals["sandboxes"] += 1
        for key in totals.keys() - {"sandboxes"}:
            totals[key] += counts.get(key, 0)
    return totals


def main() -> None:
    """Entry point: `--once` runs one loop; otherwise loop every config.WORKER_INTERVAL_SEC."""
    parser = argparse.ArgumentParser(prog="housia.worker")
    parser.add_argument("--once", action="store_true", help="run one loop and exit")
    args = parser.parse_args()

    from housia.channels import get_channel

    db.init_db()
    channel = get_channel(config.CHANNEL)
    _log(f"channel={channel.name} interval={config.WORKER_INTERVAL_SEC}s")
    while True:
        try:
            _log(str(run_once(channel)))
        except Exception:
            _log("loop failed:\n" + traceback.format_exc())
        try:
            sandbox_counts = run_sandboxes()
            if sandbox_counts["sandboxes"]:
                _log(f"sandboxes: {sandbox_counts}")
        except Exception:
            _log("sandbox loop failed:\n" + traceback.format_exc())
        if args.once:
            return
        try:
            time.sleep(config.WORKER_INTERVAL_SEC)
        except KeyboardInterrupt:
            return


if __name__ == "__main__":
    main()
