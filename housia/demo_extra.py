"""Optional local demo data, loaded after the seed on every demo reset.

Reads one extra property and portal enquiries from a JSON file (default
`instance/demo_extra.json`, which is git-ignored and never leaves this machine):

    {"property": {<columns of the properties table>},
     "threads": [{"contact_name": "...", "body": "..."}]}

The enquiries are added to the mock portal, tagged with the property's `listing_ref`, so the
worker answers them for that property. Without the file nothing happens.
"""

import json
from pathlib import Path

from housia import config

PROPERTY_COLUMNS = ("title", "address", "city", "rental_type", "rent_eur", "description", "facts",
                    "required_document", "eval_mode", "invite_limit", "reply_mode", "listing_ref")


def path() -> Path | None:
    name = config.DEMO_EXTRA_FILE
    if not name:
        return None
    p = Path(name).expanduser()
    return p if p.is_absolute() else config.ROOT / p


def load(conn, now) -> int:
    """Insert the extra property and enquiries. Returns the number of enquiries added."""
    p = path()
    if p is None or not p.is_file():
        return 0
    data = json.loads(p.read_text(encoding="utf-8"))
    stamp = now.replace(microsecond=0).isoformat()
    listing_ref = None
    prop = data.get("property")
    if prop:
        cols = [c for c in PROPERTY_COLUMNS if c in prop]
        conn.execute(
            f"INSERT INTO properties ({', '.join(cols)}, created_at) "
            f"VALUES ({', '.join('?' for _ in cols)}, ?)",
            [prop[c] for c in cols] + [stamp],
        )
        listing_ref = prop.get("listing_ref")
    added = 0
    for thread in data.get("threads") or []:
        body = (thread.get("body") or "").strip()
        if not body:
            continue
        cur = conn.execute(
            "INSERT INTO mock_threads (contact_name, listing_ref, created_at) VALUES (?, ?, ?)",
            ((thread.get("contact_name") or "Anonymous").strip(), listing_ref, stamp),
        )
        conn.execute(
            "INSERT INTO mock_messages (thread_id, sender, body, created_at) VALUES (?, 'candidate', ?, ?)",
            (cur.lastrowid, body, stamp),
        )
        added += 1
    return added
