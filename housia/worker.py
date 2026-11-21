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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from housia.channels.base import Channel


def run_once(channel: Channel) -> dict:
    """Run one worker loop on the given channel and return a summary dict.

    Pseudocode (DESIGN.md section 8):

        run_once(channel):
          if settings.worker_paused == '1': return
          # 1. record
          for msg in channel.fetch_new_messages():
              property = match msg.listing_ref to properties.listing_ref, else config.DEFAULT_PROPERTY_ID
              with tx: conversations.record_incoming(...)            # None -> already recorded
                       if conversation has no application:
                           applications.create_application(name=contact_name, source=channel.name)
                           conversations.link_application(...)
          # 2. reply
          for m in conversations.unanswered(channel.name):
              decision = reply_engine.generate_reply(property, history, m.body, name, core.applicant_url(token))
              with tx:
                  if decision.needs_landlord:
                      save_outgoing(status='draft', note=decision.reason); status -> needs_landlord; notify landlord
                  elif property.reply_mode == 'assisted':
                      save_outgoing(status='draft'); notify landlord
                  else:
                      save_outgoing(status='approved')
          # 3. send
          for out in conversations.pending_to_send(channel.name):
              try: channel.send_reply(out.external_id, out.body); mark_sent
              except ChannelError as e: mark_failed            # never resent automatically
    """
    raise NotImplementedError("A3: worker.run_once")


def main() -> None:
    """Entry point: `--once` runs one loop; otherwise loop every config.WORKER_INTERVAL_SEC."""
    parser = argparse.ArgumentParser(prog="housia.worker")
    parser.add_argument("--once", action="store_true", help="run one loop and exit")
    parser.parse_args()
    raise NotImplementedError("A3: worker.main")


if __name__ == "__main__":
    main()
