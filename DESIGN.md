# HOUSIA — design

This file is the contract for everyone building HOUSIA, people and coding agents. Read it fully
before writing code. What to build and why is in [PLAN.md](PLAN.md).

Contents: 1 Rules · 2 Architecture · 3 Units and file ownership · 4 Git and agents ·
5 Database · 6 Shared helpers · 7 Service contracts · 8 Channels and worker ·
9 Pages, routes and forms · 10 Seed data · 11 Configuration · 12 Done checklist

---

## 1. Rules

1. **One owner per file.** Every file belongs to exactly one unit (section 3). Only that unit
   edits it.
2. **Frozen files** belong to the skeleton (S0). Nobody edits them after the skeleton is merged,
   except the main backend person, in a single commit on `main`, announced to the team.
3. **Need a change outside your unit?** Do not make it. Tell the owner. If it is a contract
   change (schema, a signature, a route, a template variable), the main backend person updates
   this file and the frozen file in the same commit.
4. **Code against the contract, not the implementation.** The skeleton contains a stub for every
   function and template. Other units may be unfinished; call their documented signature anyway
   and use fakes in your tests.
5. **English** for interface text, code and comments.
6. **No new dependencies** without asking the main backend person (`pyproject.toml` and
   `uv.lock` are frozen). Python and packages are managed with `uv`; do not use `pip`.
7. **No personal data goes to an AI model.** Text for a model is sent only through
   `housia.llm.complete`, which masks names, contact details and identity numbers first
   (section 7, "privacy.py and llm.py"). No other file imports a model SDK, except
   `channels/idealista.py` and `channels/badi.py` for driving the browser.

## 2. Architecture

```
Browser (landlord pages, applicant pages, mock inbox)
        │  HTML forms, full page reloads
        ▼
housia/web/*.py        Flask blueprints. Parse the request, call services, render a template.
        │
        ▼
housia/services/*.py   Business rules. Plain functions on a database connection.
        │
        ▼
housia/db.py + schema.sql   SQLite

housia/worker.py       Separate process. Loop: channel → services → channel.
housia/channels/*.py   Read and send portal messages (mock, Idealista, Badi).
```

Layering rules:
- `web` and `worker` may import any service and `core`.
- A service imports only `housia.core`, `housia.db`, `housia.privacy` and `housia.llm`.
  **Services never import each other.**
- Only `channels/` and `worker.py` touch the browser automation. The web app never does.
- Templates contain no business logic. They show what the route gives them.

Conventions:
- Service functions take `conn` first and `now` last: `book(conn, application_id, slot_id, now)`.
  They never call `datetime.now()`. The caller passes `core.now(conn)`.
- Rule violations raise `core.DomainError("message for the user")`.
- Every POST route follows this pattern:

```python
@bp.post("/a/<token>/book")
def book(token):
    try:
        with db.tx() as conn:                      # BEGIN IMMEDIATE … COMMIT / ROLLBACK
            app_row = applications.get_by_token(conn, token)
            scheduling.book(conn, app_row["id"], int(request.form["slot_id"]), core.now(conn))
        flash("Viewing booked.", "ok")
    except core.DomainError as e:
        flash(str(e), "error")
    return redirect(url_for("applicant.page", token=token))
```

- GET routes read with `db.tx()` too and pass rows straight to the template.
- Rows are `sqlite3.Row`. In templates use column names: `{{ application.name }}`.
- Dates are stored as ISO text in local time without zone: `2026-11-22T10:00:00`.
- IDs are integers. Applicant URLs use `applications.token`, never the id.
- No real file uploads. "Uploading" a document means choosing one of the bundled fake files.

## 3. Units and file ownership

All paths are relative to the repo root. `S0` is built first and merged before anyone else starts.

### S0 — Skeleton (main backend) — frozen after merge

`housia/__init__.py` (app factory, registers every blueprint, context processor, `tick` hook),
`housia/config.py`, `housia/db.py`, `housia/schema.sql`, `housia/core.py`,
`housia/channels/__init__.py`, `housia/channels/base.py`, `housia/services/__init__.py`,
`housia/web/__init__.py`, `tests/conftest.py`, `tests/test_core.py`, `tests/test_app.py`,
`run.py`, `pyproject.toml`, `uv.lock`, `.python-version`, `.gitignore`,
`.env.example`, `README.md`, `PLAN.md`, `DESIGN.md`.

The project uses `uv` with Python 3.12. `pyproject.toml` holds: `flask`, `python-dotenv`,
`pypdf` (text of uploaded PDFs), `openai`, `browser-use==1.0.6`, and `pytest` as a dev
dependency. Set up with `uv sync`. Run everything through `uv run`.

The skeleton also creates **a stub of every file listed below** (functions with the documented
signature that raise `NotImplementedError` or return an empty value; templates with a title
only). After the merge, those stubs belong to their units.

### Main backend — message automation

| Unit | Files |
|---|---|
| **A1** Mock channel | `housia/channels/mock.py`, `housia/web/mock_inbox.py`, `tests/test_mock_channel.py` |
| **A2** Idealista channel | `housia/channels/idealista.py`, `scripts/idealista_probe.py`, `tests/test_idealista_channel.py` |
| **A3** Conversations and worker | `housia/services/conversations.py`, `housia/worker.py`, `tests/test_conversations.py`, `tests/test_worker.py` |
| **A4** Reply engine | `housia/services/reply_engine.py`, `tests/test_reply_engine.py` |
| **A5** Conversation routes | `housia/web/conversations.py`, `tests/test_web_conversations.py`, `tests/test_block1_flow.py` (end-to-end: mock inbox → worker → reply) |
| **A6** Badi channel (last) | `housia/channels/badi.py` |
| **A7** Privacy guard and model gateway | `housia/privacy.py`, `housia/llm.py`, `tests/test_privacy.py`, `tests/test_llm.py` |
| **A8** Document check for the landlord | `housia/services/doc_summary.py`, `tests/test_doc_summary.py` |

### Backend 2 — rental workflow

| Unit | Files |
|---|---|
| **B1** Properties and dashboard | `housia/services/properties.py`, `housia/web/dashboard.py`, `housia/web/properties.py`, `tests/test_properties.py` |
| **B2** Applications and documents | `housia/services/applications.py`, `housia/services/documents.py`, `housia/web/applications.py`, `tests/test_applications.py`, `tests/test_documents.py` |
| **B3** Evaluation | `housia/services/evaluation.py`, `housia/web/evaluation.py`, `tests/test_evaluation.py` |
| **B4** Scheduling | `housia/services/scheduling.py`, `housia/web/schedule.py`, `tests/test_scheduling.py` |
| **B5** Post-viewing and contract | `housia/services/postviewing.py`, `housia/services/contracts.py`, `housia/web/contract.py`, `tests/test_postviewing.py`, `tests/test_contracts.py` |
| **B6** Applicant routes | `housia/web/applicant.py`, `tests/test_web_applicant.py` |
| **B7** Demo tools and seed | `housia/web/demo.py`, `housia/seed.py`, `scripts/make_demo_pdfs.py`, `housia/static/demo/*`, `tests/test_seed.py` |

### Frontend — templates and styles

| Unit | Files |
|---|---|
| **C1** Base and styles (first) | `housia/templates/base.html`, `housia/templates/base_mobile.html`, `housia/templates/_macros.html`, `housia/static/style.css` |
| **C2** Dashboard and properties | `dashboard.html`, `property.html`, `property_form.html` |
| **C3** Applications | `applications.html`, `application.html`, `evaluation.html` |
| **C4** Schedule and contract | `schedule.html`, `contract.html` |
| **C5** Applicant (mobile) | `apply.html`, `applicant.html` |
| **C6** Conversations and mock inbox | `conversations.html`, `conversation.html`, `mock_inbox.html`, `mock_thread.html`, `mock_candidate.html` |
| **C7** Demo pages | `demo.html`, `inbox.html` |

All templates live in `housia/templates/`.

Frontend rules, so several frontend agents can work at once:
- C1 finishes first. It defines every shared class and macro (buttons, badges, cards, tables,
  forms, flash messages, status badge, "Simulation" badge, phone frame) and documents them in a
  comment at the top of `_macros.html`.
- Units C2–C7 **do not edit `style.css`**. Page-specific CSS goes in
  `housia/static/pages/<template-name>.css`, loaded in the template's `{% block head %}`.
- Landlord pages extend `base.html`. Applicant and mock-candidate pages extend
  `base_mobile.html` and must look right at 390 px wide.
- Form `action`, `method` and field `name` values are fixed by section 9. Do not rename them.

### Dependencies between units

Nothing blocks on another unit's code, only on S0. Recommended start order when a person has
fewer agents than units:

- Main backend: A2 probe → A7, A1, A3, A4 together → A5 → (block 2) A2, A8 → A6
- Backend 2: B7 seed, B2, B4 together → B1, B6 → (block 2) B3, B5
- Frontend: C1 → all others together; `evaluation.html`, `contract.html` and
  `property_form.html` can wait for block 2

The two blocks are described in PLAN.md, "Timing".

## 4. Git and agents

### Branches

- `main` always runs. Only merged, tested units go in.
- One branch per unit: `unit/b4-scheduling`, `unit/c5-applicant`, …
- Merge a unit as soon as its own tests pass. Small and often.
- Before merging: `git fetch && git rebase origin/main`, run `uv run pytest`, then merge. Because
  files do not overlap, the rebase should never conflict. If it does, someone broke rule 1:
  stop and find out who.

### One worktree per agent

Each agent gets its own folder, so agents on one machine never share a working directory:

```bash
git worktree add ../housia-b4 -b unit/b4-scheduling origin/main
cd ../housia-b4
uv sync                                      # fast: packages come from uv's cache
PORT=5004 HOUSIA_DB=instance/b4.db uv run python run.py
```

Use a different `PORT` and `HOUSIA_DB` per worktree. `instance/` is git-ignored.

### Brief to give each agent

```
You are building unit <ID> of HOUSIA. Read DESIGN.md completely first.

Your files (edit only these, they already exist as stubs):
<list from section 3>

Do:
- Implement the contract for your unit in sections 7–9 of DESIGN.md.
- Write the tests named for your unit. Use the fixtures in tests/conftest.py.
- Other units may still be stubs. Do not implement or edit them. Use fakes in tests.

Do not:
- Edit any file outside your list, including frozen files, style.css or pyproject.toml.
- Change a signature, route, form field or template variable. If the contract is wrong or
  incomplete, stop and report exactly what needs to change.

Finish when: `uv run pytest tests/<your tests>` passes and `uv run python run.py` starts. Report what you
built, what you could not verify, and any contract problem you found.
```

## 5. Database

`housia/schema.sql` (frozen). `db.reset_db()` drops everything, runs this file and runs the seed.

```sql
CREATE TABLE properties (
  id                      INTEGER PRIMARY KEY,
  title                   TEXT NOT NULL,
  address                 TEXT NOT NULL,
  city                    TEXT NOT NULL,
  rental_type             TEXT NOT NULL CHECK (rental_type IN ('residential','temporary')),
  rent_eur                INTEGER NOT NULL,
  description             TEXT NOT NULL DEFAULT '',
  facts                   TEXT NOT NULL DEFAULT '',   -- plain text the reply engine may quote
  required_document       TEXT NOT NULL,              -- e.g. 'Latest payslip'
  eval_mode               TEXT NOT NULL DEFAULT 'assisted' CHECK (eval_mode  IN ('assisted','automatic')),
  invite_limit            INTEGER NOT NULL DEFAULT 3, -- max applicants with calendar access
  reply_mode              TEXT NOT NULL DEFAULT 'assisted' CHECK (reply_mode IN ('assisted','automatic')),
  listing_ref             TEXT,                       -- listing id or URL on the portal
  finalist_application_id INTEGER REFERENCES applications(id),
  contract_status         TEXT NOT NULL DEFAULT 'none' CHECK (contract_status IN ('none','pending','sent','signed')),
  signed_contract_file    TEXT,
  created_at              TEXT NOT NULL
);

CREATE TABLE applications (
  id              INTEGER PRIMARY KEY,
  property_id     INTEGER NOT NULL REFERENCES properties(id),
  token           TEXT NOT NULL UNIQUE,               -- used in applicant URLs
  name            TEXT NOT NULL,
  email           TEXT NOT NULL DEFAULT '',
  phone           TEXT NOT NULL DEFAULT '',
  source          TEXT NOT NULL CHECK (source IN ('link','idealista','badi','mock','fotocasa','whatsapp','phone')),
  preferences     TEXT NOT NULL DEFAULT '',
  availability    TEXT NOT NULL DEFAULT '',           -- comma list of: morning,afternoon,weekend
  status          TEXT NOT NULL DEFAULT 'new' CHECK (status IN (
                    'new','docs_requested','docs_uploaded','docs_correction','docs_approved',
                    'invited','booked','attended','absent','finalist','completed','closed')),
  doc_file        TEXT,
  doc_note        TEXT,                               -- landlord's correction note
  doc_summary     TEXT,                               -- AI check of the document, written by A8
  calendar_access INTEGER NOT NULL DEFAULT 0,
  invited_by      TEXT CHECK (invited_by IN ('landlord','auto')),
  created_at      TEXT NOT NULL
);

CREATE TABLE slots (
  id                    INTEGER PRIMARY KEY,
  property_id           INTEGER NOT NULL REFERENCES properties(id),
  starts_at             TEXT NOT NULL,
  duration_min          INTEGER NOT NULL DEFAULT 30,
  booked_application_id INTEGER REFERENCES applications(id),
  offer_application_id  INTEGER REFERENCES applications(id),
  offer_expires_at      TEXT,
  attendance            TEXT CHECK (attendance IN ('attended','absent'))
);
-- one active booking per application
CREATE UNIQUE INDEX one_booking_per_application
  ON slots(booked_application_id) WHERE booked_application_id IS NOT NULL;

CREATE TABLE waitlist (
  id             INTEGER PRIMARY KEY,
  slot_id        INTEGER NOT NULL REFERENCES slots(id) ON DELETE CASCADE,
  application_id INTEGER NOT NULL REFERENCES applications(id),
  joined_at      TEXT NOT NULL,
  UNIQUE (slot_id, application_id)
);

CREATE TABLE notifications (
  id             INTEGER PRIMARY KEY,
  property_id    INTEGER REFERENCES properties(id),
  application_id INTEGER REFERENCES applications(id),  -- NULL = for the landlord
  title          TEXT NOT NULL,
  body           TEXT NOT NULL DEFAULT '',
  created_at     TEXT NOT NULL,
  is_read        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE conversations (
  id             INTEGER PRIMARY KEY,
  property_id    INTEGER NOT NULL REFERENCES properties(id),
  channel        TEXT NOT NULL CHECK (channel IN ('mock','idealista','badi')),
  external_id    TEXT NOT NULL,                        -- conversation id on the portal
  contact_name   TEXT NOT NULL DEFAULT '',
  application_id INTEGER REFERENCES applications(id),
  status         TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','needs_landlord')),
  created_at     TEXT NOT NULL,
  UNIQUE (channel, external_id)
);

CREATE TABLE messages (
  id              INTEGER PRIMARY KEY,
  conversation_id INTEGER NOT NULL REFERENCES conversations(id),
  direction       TEXT NOT NULL CHECK (direction IN ('in','out')),
  body            TEXT NOT NULL,
  external_id     TEXT,                                -- set for incoming; used to dedupe
  status          TEXT NOT NULL CHECK (status IN ('received','draft','approved','sent','failed','discarded')),
  in_reply_to     INTEGER REFERENCES messages(id),
  note            TEXT,                                -- why flagged, or the send error
  created_at      TEXT NOT NULL,
  sent_at         TEXT,
  UNIQUE (conversation_id, external_id)
);
-- at most one live reply per incoming message
CREATE UNIQUE INDEX one_reply_per_incoming
  ON messages(in_reply_to) WHERE in_reply_to IS NOT NULL AND status <> 'discarded';

-- The mock portal. Separate on purpose: HOUSIA reaches it only through channels/mock.py.
CREATE TABLE mock_threads (
  id           INTEGER PRIMARY KEY,
  contact_name TEXT NOT NULL,
  listing_ref  TEXT,
  created_at   TEXT NOT NULL
);
CREATE TABLE mock_messages (
  id         INTEGER PRIMARY KEY,
  thread_id  INTEGER NOT NULL REFERENCES mock_threads(id),
  sender     TEXT NOT NULL CHECK (sender IN ('candidate','landlord')),
  body       TEXT NOT NULL,
  created_at TEXT NOT NULL,
  fetched    INTEGER NOT NULL DEFAULT 0               -- 1 once the channel has handed it over
);

CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
-- keys: clock_offset_min (default '0'), worker_paused ('0' or '1')
```

### Application status flow

| From | To | Triggered by | Unit |
|---|---|---|---|
| — | `new` | application created | B2 |
| `new` | `docs_requested` | landlord requests the document | B2 |
| `docs_requested`, `docs_correction` | `docs_uploaded` | applicant submits a file | B2 |
| `docs_uploaded` | `docs_correction` | landlord asks for a correction | B2 |
| `docs_uploaded` | `docs_approved` | landlord approves | B2 |
| `docs_uploaded`, `docs_approved` | `invited` | calendar access granted (landlord, or evaluation) | core |
| `invited` | `booked` | books a slot or accepts an offer | B4 |
| `booked` | `invited` | booking cancelled | B4 |
| `booked` | `attended` / `absent` | landlord records attendance | B5 |
| `attended` | `finalist` | landlord selects the final candidate | B5 |
| `finalist` | `completed` | signed contract attached | B5 |
| any other | `closed` | signed contract attached for someone else | B5 |

## 6. Shared helpers (S0, frozen, fully implemented in the skeleton)

```python
# housia/db.py
def get_conn() -> sqlite3.Connection        # Row factory, foreign keys on
def tx()                                    # context manager: BEGIN IMMEDIATE, commit or rollback
def init_db() -> None                       # create tables if missing
def reset_db() -> None                      # drop all, create, seed.run()

# housia/core.py
class DomainError(Exception)                # str(e) is shown to the user
APPLICATION_STATUSES, TIME_BANDS = ('morning', 'afternoon', 'weekend')
def now(conn) -> datetime                   # real time + clock_offset_min
def get_setting(conn, key, default=None) -> str | None
def set_setting(conn, key, value) -> None
def notify(conn, *, property_id, application_id, title, body, now) -> None   # application_id=None → landlord
def set_status(conn, application_id, status) -> None
def invited_count(conn, property_id) -> int                # applications with calendar_access = 1
def grant_calendar_access(conn, application_id, invited_by, now) -> None
    # allowed from docs_uploaded or docs_approved; raises DomainError when invite_limit is reached;
    # sets calendar_access=1, invited_by, status='invited'; notifies the applicant
def time_band(dt: datetime) -> str          # weekend | morning (weekday before 14:00) | afternoon
def applicant_url(token) -> str             # config.BASE_URL + /a/<token>
```

The app factory also:
- runs `scheduling.tick(conn, core.now(conn))` before every request, so expired offers move on;
- gives every template: `now`, `clock_offset_min`, `unread_count`, `nav_properties`,
  `worker_paused`;
- provides the template filter `dt`: `{{ slot.starts_at | dt }}` → `Mon 23 Nov, 09:00`. It takes
  a stored ISO string or a `datetime`, and an optional `strftime` format.

Notes:
- In templates `now` is a `datetime`, while stored dates are ISO text. Do not compare them in
  a template. Routes pass ready-made flags and states instead (for example the `state` of each
  slot from `slots_for_applicant`).
- `invite_limit` counts every applicant who was ever given calendar access, including those
  who later cancel, miss the viewing or are closed. That is intended: it is the number of
  people the landlord is willing to invite.
- `core.set_status` checks that the status name is valid, not that the move is allowed. Each
  unit checks its own transitions (status flow table, section 5).

`tests/conftest.py` provides `conn` (fresh in-memory database with the schema), `client` (Flask
test client on a temporary database) and `t0` (a fixed `datetime`, a Monday at 09:00).

## 7. Service contracts

All in `housia/services/`. `Row` means `sqlite3.Row`. Missing ids raise `DomainError`.

### properties.py — B1
```python
def list_properties(conn) -> list[Row]
def get_property(conn, property_id) -> Row
def create_property(conn, data: dict, now) -> int       # keys = editable columns of properties
def update_property(conn, property_id, data: dict) -> None
def property_stats(conn, property_id) -> dict           # applications, invited, booked, open_conversations, needs_landlord
def upcoming_viewings(conn, now, limit=10) -> list[Row] # slot columns + property_title + applicant_name
def public_link(property_id) -> str                     # config.BASE_URL + /apply/<id>
def copy_messages(prop: Row, link: str) -> dict[str, str]   # keys: idealista, fotocasa, whatsapp
```

### applications.py — B2
```python
def create_application(conn, property_id, data: dict, source: str, now) -> int
    # data keys: name (required), email, phone, preferences, availability (list[str])
    # generates token; notifies the landlord
def update_details(conn, application_id, data: dict) -> None   # same keys; used when a portal contact completes their details
def get_application(conn, application_id) -> Row
def get_by_token(conn, token) -> Row
def list_for_property(conn, property_id) -> list[Row]   # ordered by created_at
```

### documents.py — B2
```python
def demo_files() -> list[str]                           # fake applicant documents in static/demo/
def request_document(conn, application_id, now) -> None
def upload_document(conn, application_id, file_name, now) -> None   # file_name must be in demo_files()
def approve_document(conn, application_id, now) -> None
def request_correction(conn, application_id, note, now) -> None
```
Granting calendar access directly is `core.grant_calendar_access(..., invited_by='landlord', ...)`.

### evaluation.py — B3
```python
@dataclass
class Proposal:
    application_id: int; name: str; position: int
    score: int; total_slots: int; explanation: str      # "Can attend 3 of 4 open slots. Applied 2nd."

@dataclass
class EvaluationResult:
    mode: str                        # 'assisted' | 'automatic'
    proposals: list[Proposal]        # ranked, best first
    remaining: int                   # invite_limit - invited_count, before this run
    invited_ids: list[int]           # automatic: who was invited now; assisted: []
    left_out_ids: list[int]          # automatic: eligible but over the limit

def rank(conn, property_id, now) -> list[Proposal]
def evaluate(conn, property_id, now) -> EvaluationResult
def invite(conn, property_id, application_ids: list[int], now) -> None   # assisted confirmation
```
- Eligible: `status = 'docs_approved'`.
- Score: number of future slots of the property with no booking and no offer whose
  `core.time_band(starts_at)` is in the applicant's `availability`. Higher first.
- Tie-break: earlier `created_at`.
- `evaluate` in assisted mode changes nothing. In automatic mode it calls
  `core.grant_calendar_access(..., invited_by='auto')` for the top `remaining` proposals.
- `invite` raises `DomainError` if the selection exceeds `remaining`.

### scheduling.py — B4
```python
def create_slot(conn, property_id, starts_at: datetime, duration_min, now) -> int   # must be in the future
def delete_slot(conn, slot_id) -> None                  # only if no booking, offer or waitlist
def list_slots(conn, property_id) -> list[dict]
    # each: id, starts_at, duration_min, attendance, booked (Row|None), offer ({application: Row, expires_at}|None),
    #       waitlist (list[Row] of applications, in order)
def slots_for_applicant(conn, application_id, now) -> list[dict]
    # each: id, starts_at, duration_min, state, offer_expires_at, waitlist_position
    # state: 'free' | 'mine' | 'taken' | 'waiting' | 'offered_to_me' | 'held' (offered to someone else)
def book(conn, application_id, slot_id, now) -> None
def cancel_booking(conn, slot_id, by: str, now) -> None  # by: 'applicant' | 'landlord'
def join_waitlist(conn, application_id, slot_id, now) -> None
def leave_waitlist(conn, application_id, slot_id, now) -> None
def accept_offer(conn, application_id, slot_id, now) -> None
def decline_offer(conn, application_id, slot_id, now) -> None
def tick(conn, now) -> int                              # expire overdue offers; returns how many
```
Rules:
- `book`: applicant has `calendar_access`; slot is in the future, has no booking and no offer;
  applicant has no other booking for this property. Otherwise `DomainError`. The check and the
  write happen in the caller's transaction, so two applicants can never hold one slot.
- `join_waitlist`: slot must be booked by someone else or held; once per slot.
- `cancel_booking`: clears the booking, sets the applicant back to `invited`, then runs the relay.
- **Relay** (one private function used by cancel, decline and tick): take the first person on the
  waitlist. If there is one, set `offer_application_id` and
  `offer_expires_at = min(now + 30 min, starts_at)`, and send **one** notification to that
  applicant and one to the landlord. If the waitlist is empty, the slot becomes free.
- `accept_offer`: only by the offered applicant before expiry. Books the slot, removes them from
  the waitlist, clears the offer. If they had another booking on this property, that booking is
  cancelled first (its own relay runs).
- `decline_offer` and expiry in `tick`: remove that person from the waitlist, clear the offer,
  run the relay again.

### postviewing.py — B5
```python
def set_attendance(conn, slot_id, value: str, now) -> None   # 'attended' | 'absent'; slot must be booked
def attended_applications(conn, property_id) -> list[Row]
def select_finalist(conn, property_id, application_id, now) -> None   # must have attended; one per property
```

### contracts.py — B5
```python
def demo_contract_files() -> list[str]                  # fake signed contracts in static/demo/
def set_contract_status(conn, property_id, status: str, now) -> None   # 'pending' | 'sent'; needs a finalist
def attach_signed(conn, property_id, file_name, now) -> None
    # requires status 'sent'; sets 'signed' + signed_contract_file; finalist → 'completed';
    # every other application of the property → 'closed' with a polite notification
```
The contract can never be `signed` without a file.

### conversations.py — A3
```python
def record_incoming(conn, channel: str, msg: IncomingMessage, property_id: int, now) -> int | None
    # creates the conversation if new; returns the new message id, or None if already recorded
def get_conversation(conn, conversation_id) -> Row
def list_conversations(conn, property_id) -> list[dict]  # conversation columns + last_message, pending_drafts
def get_thread(conn, conversation_id) -> list[Row]       # messages, oldest first
def link_application(conn, conversation_id, application_id) -> None
def set_conversation_status(conn, conversation_id, status) -> None
def save_outgoing(conn, conversation_id, body, status, in_reply_to, note, now) -> int   # status: 'draft' | 'approved'
def approve(conn, message_id, body: str | None, now) -> None   # draft → approved; optional edited text
def discard(conn, message_id) -> None                     # draft → discarded
def unanswered(conn, channel: str) -> list[Row]           # incoming messages with no reply row at all
    # A discarded draft still counts as a reply row: discarding means the landlord takes over
    # that message, so the worker does not draft again. A manual reply is still possible.
def pending_to_send(conn, channel: str) -> list[Row]      # approved outgoing + conversation external_id
def mark_sent(conn, message_id, now) -> None
def mark_failed(conn, message_id, error: str) -> None
```

### reply_engine.py — A4
```python
@dataclass
class ReplyDecision:
    text: str
    needs_landlord: bool        # True = do not send without the landlord
    reason: str                 # why it was flagged, or ''

def generate_reply(prop: Mapping, history: list[Mapping], incoming: str,
                   contact_name: str, applicant_link: str) -> ReplyDecision
```
- Pure function: no database, no browser. `history` items have `direction` and `body`.
- Two engines chosen by `config.REPLY_ENGINE`: `template` (no API key, keyword rules) and `llm`.
- First message of a conversation: greet by name, give the key facts (rent, type, city), say
  which document is needed, and give `applicant_link` as the next step.
- Later messages: answer only from `prop` columns and `prop['facts']`. If the answer is not
  there, set `needs_landlord=True` with a `reason` and a holding reply. Never invent facts.
- Every reply ends with a line saying it was written by the landlord's assistant.
- The `llm` engine falls back to `template` on any error.
- The `llm` engine calls the model only through `llm.complete(system, user, known)`, passing the
  contact name in `known`. It never imports a model SDK.

### privacy.py and llm.py — A7

Purpose: no real name, contact detail or identity number leaves the machine in a model request.

A model cannot read encrypted text, so the values are **replaced with placeholders** before the
call and put back afterwards. The table that links placeholders to real values exists only in
memory for that one call.

```python
# housia/privacy.py
class PrivacyError(Exception): ...

@dataclass
class Masked:
    text: str
    mapping: dict[str, str]        # placeholder → real value. Never stored, logged or sent.

def known_values(application: Mapping) -> dict[str, str]   # {'NAME': ..., 'EMAIL': ..., 'PHONE': ...}
def mask(text: str, known: Mapping[str, str] | None = None) -> Masked
def unmask(text: str, mapping: dict[str, str]) -> str
def assert_clean(text: str, mapping: dict[str, str]) -> None   # PrivacyError if a real value is still in text

# housia/llm.py
def complete(system: str, user: str, known: Mapping[str, str] | None = None) -> str
    # 1. masked = privacy.mask(user, known)      2. privacy.assert_clean(masked.text, masked.mapping)
    # 3. call the model with system + masked.text  4. return privacy.unmask(answer, masked.mapping)
    # Raises LLMError on any failure (also when REPLY_MODEL or OPENAI_API_KEY is missing).
    # `system` must be fixed text with no personal data.
    # Uses the OpenAI Responses API with store=False, so OpenAI does not keep the request.
```

What `mask` replaces:
- **Known values** from the database (`known`): the applicant's full name and each part of it,
  email and phone. Matched without regard to case or accents.
- **Patterns**: email addresses; phone numbers (Spanish 9-digit and `+34`); DNI (8 digits and a
  letter); NIE (X, Y or Z, 7 digits, a letter); passport numbers (3 letters and 6 digits); IBAN;
  payment card numbers; any other run of 8 or more digits.
- **Labelled fields in documents**: the value after labels such as `Name:`, `Full name:`,
  `Nombre:`, `DNI:`, `NIE:`, `Passport:`, `IBAN:`, `Address:`, `Dirección:`.

Placeholders look like `[NAME_1]`, `[ID_1]`, `[IBAN_1]`, `[PHONE_1]`, `[EMAIL_1]`,
`[ADDRESS_1]`, `[CARD_1]`, `[NUMBER_1]`. The same value gets the same placeholder within one call, so the model can still
reason ("the name on the payslip matches the applicant").

Known limits, to say out loud rather than hide:
- A name that is not in the database and not next to a label (for example a flatmate mentioned
  in free text) is not detected.
- The browser agent (A2) looks at the portal page as it is, with real names and messages on
  screen. Masking cannot apply there. See section 8.

### doc_summary.py — A8
```python
def summarize_for_landlord(application_id: int) -> None
```
- Called by the applicant upload route (B6) **after** its transaction has committed.
- Opens its own short transactions: read the application and property → no transaction during
  the model call → write the result. (This is the one service that does not take `conn`.)
- Reads the text of the uploaded file from `housia/static/demo/` and asks the model, through
  `llm.complete(..., known=privacy.known_values(application))`: what the document is, whether it
  matches `property.required_document`, and what is missing or unclear.
- Saves the answer in `applications.doc_summary` and sends it to the landlord as a notification.
  Because `llm.complete` restores the placeholders locally, the landlord reads real names.
- It never decides anything. The landlord still approves or asks for a correction.
- It never raises. On any error, or with `REPLY_ENGINE=template`, the summary is
  "Document received: <file>. Automatic check not available."

## 8. Channels and worker

### Interface — `housia/channels/base.py` (S0, frozen)
```python
@dataclass
class IncomingMessage:
    external_conversation_id: str
    external_message_id: str       # stable id; if the portal shows none, use make_message_id()
    contact_name: str
    text: str
    received_at: str | None = None
    listing_ref: str | None = None

class ChannelError(Exception): ...

class Channel(Protocol):
    name: str                      # 'mock' | 'idealista' | 'badi'
    def fetch_new_messages(self) -> list[IncomingMessage]: ...
    def send_reply(self, external_conversation_id: str, text: str) -> None: ...   # raises ChannelError

def make_message_id(conversation_id: str, text: str, received_at: str | None) -> str   # sha1 hex

# housia/channels/__init__.py
def get_channel(name: str) -> Channel
    # returns MockChannel() from channels/mock.py, IdealistaChannel() from channels/idealista.py
    # or BadiChannel() from channels/badi.py. Each takes no arguments. Imports are lazy, so the
    # web app and tests never import browser-use.
```
Both methods are synchronous. A channel that uses async code wraps it with `asyncio.run`.
`fetch_new_messages` may return a message twice; deduplication is the job of
`conversations.record_incoming`.

### A1 — mock channel
- `MockChannel.fetch_new_messages`: candidate rows in `mock_messages` with `fetched = 0`; marks
  them fetched. `send_reply`: inserts a `landlord` row in the thread.
- Routes in `web/mock_inbox.py` render the fake portal (section 9). It must look like a
  separate website, not like HOUSIA.

### A2 — Idealista channel (`browser-use`)

Facts from the `browser-use` docs, checked 2026-11-21. Check docs.browser-use.com again before
relying on details; the API changed a lot between versions.

- Already in `pyproject.toml` as `browser-use==1.0.6`. Run `uv run browser-use install` once
  for a local Chromium.
- Logged-in session: `Browser('chromium', user_data_dir=config.CHROME_PROFILE_DIR)` keeps its
  own logins between runs. Log in to Idealista **by hand** once in that window. Do not automate
  the login. (Alternative: `Browser('chrome')` attaches to your open Chrome after you allow
  remote debugging at `chrome://inspect/#remote-debugging`.)
- Model: the team uses OpenAI. `from browser_use import ChatOpenAI`, then
  `ChatOpenAI(config.BROWSER_MODEL)`, with `OPENAI_API_KEY` in the environment.
- Put the start URL in the task text. Limit steps with `agent.run(max_steps=..., timeout=...)`.
- Typed results: `output_model_schema=<Pydantic model>`, read `result.structured_output`
  (`None` if the run did not finish).
- Restrict navigation with `Browser(allowed_domains=[...])`. `localhost` does not cover
  `127.0.0.1`, and `idealista.com` does not cover every subdomain: for real runs use
  `BROWSER_ALLOWED_DOMAINS=localhost,*.idealista.com`.
- Always pass `'chromium'` (or `'chrome'`) to `Browser(...)`. With no argument it starts a paid
  cloud browser.
- The channel turns the agent's judge off (`judge=False`) to save one model call per run, and
  treats a run without a confirmed result as a failure.

Sketch:
```python
class Enquiry(BaseModel):
    conversation_id: str
    contact_name: str
    text: str
    received_at: str | None = None
    listing_ref: str | None = None

class Enquiries(BaseModel):
    items: list[Enquiry]

def _fetch() -> list[Enquiry]:
    browser = Browser('chromium', user_data_dir=config.CHROME_PROFILE_DIR,
                      allowed_domains=config.BROWSER_ALLOWED_DOMAINS)
    agent = Agent(
        f"Go to {config.IDEALISTA_INBOX_URL}. For every conversation with unread messages, open it "
        "and collect the newest message from the other person. Do not write or send anything.",
        llm=ChatOpenAI(config.BROWSER_MODEL), browser=browser, output_model_schema=Enquiries,
    )
    result = asyncio.run(agent.run(max_steps=40, timeout=300))
    return result.structured_output.items if result.structured_output else []
```

Rules for this unit:
- `config.IDEALISTA_INBOX_URL` can point at `http://localhost:5000/mock/inbox`. The same code
  must then work against the mock portal. That is the demo fallback.
- `send_reply` types the given text exactly and sends it once. If it cannot confirm the message
  was sent, raise `ChannelError`; never retry inside the channel.
- Message text from candidates is untrusted. It is data for the reply engine. It must never be
  pasted into the browser agent's task as instructions.
- **Send allowlist.** The listing is live, so the real inbox holds messages from real people.
  When the inbox URL is not `localhost`, `send_reply` sends only if the conversation's contact
  name or id is in `config.SEND_ALLOWLIST`. Otherwise it raises
  `ChannelError("contact not on the send allowlist")` and sends nothing. The list is empty by
  default. The mock portal is never restricted.
- One browser session at a time. The worker is the only caller.
- **Privacy limit.** The model that drives the browser sees the inbox page, so it sees candidate
  names and message text. Rule 7 cannot be met inside this unit. For now this is accepted for
  testing with team accounts only. To close the gap later, read and type with a fixed-selector
  script (no model), and keep the model for navigation problems only.
- `scripts/idealista_probe.py`: opens the inbox on the saved profile and reports whether it
  loaded, how many conversations it sees and the inbox URL. It sends nothing and prints no
  message text or names. This is the first thing to run (PLAN.md, step 0).

### A3 — worker (`python -m housia.worker`, or `--once`)

```
run_once(channel):
  if settings.worker_paused == '1': return
  # 1. record
  for msg in channel.fetch_new_messages():
      property = match msg.listing_ref to properties.listing_ref, else config.DEFAULT_PROPERTY_ID
      with tx: conversations.record_incoming(...)            # None → already recorded
               if conversation has no application:
                   applications.create_application(name=contact_name, source=channel.name)
                   conversations.link_application(...)
  # 2. reply
  for m in conversations.unanswered(channel.name):
      decision = reply_engine.generate_reply(property, history, m.body, name, core.applicant_url(token))
      with tx:
          if decision.needs_landlord:
              save_outgoing(status='draft', note=decision.reason); status → needs_landlord; notify landlord
          elif property.reply_mode == 'assisted':
              save_outgoing(status='draft'); notify landlord
          else:
              save_outgoing(status='approved')
  # 3. send
  for out in conversations.pending_to_send(channel.name):
      try: channel.send_reply(out.external_id, out.body); mark_sent
      except ChannelError as e: mark_failed            # never resent automatically
```
- No transaction is open while a model or the browser is working. They take seconds, and an
  open write transaction would block the web app.
- `run_once` returns counts: `paused`, `recorded`, `drafted`, `approved`, `sent`, `failed`
  (failed sends), `errors` (messages that could not be recorded or answered; each is printed).
- The application is created in its own transaction, after the message is recorded, and the
  reply step tries again while a conversation has no application. So a failure there never
  loses a message.
- If the worker stops between steps, the next loop picks the message up again from
  `unanswered`. The `one_reply_per_incoming` index stops a second reply.
- The landlord approving a draft only sets it to `approved`. The worker sends it on its next
  loop. The web app never sends.
- Loop interval: `config.WORKER_INTERVAL_SEC`.

### A6 — Badi
Same interface, same approach as A2. Only after everything else works.

## 9. Pages, routes and forms

Blueprint name = file name in `housia/web/`; each file exposes it as `bp`. All POST routes
redirect back to the page they came from and use `flash(message, 'ok' | 'error')`.

Links, form actions and redirects use the **literal paths** in this section
(`action="/a/{{ application.token }}/book"`). Do not use `url_for` to reach another unit's
route; endpoint function names are not part of the contract.

Redirect targets for POST routes whose path has no page id:
- `/slots/<id>/delete`, `/slots/<id>/cancel`, `/slots/<id>/attendance` → `/properties/<property_id>/schedule`
  (the attendance form is on `schedule.html`).
- `/messages/<id>/approve`, `/messages/<id>/discard` → `/conversations/<conversation_id>`.
- `/worker/pause` → the page it was sent from (`request.referrer`), else `/`. Its form is on
  `conversations.html`.
- `POST /properties` → `/properties/<new id>`; `POST /properties/<id>` → `/properties/<id>`.
  On a validation error, back to the form.

Template blocks provided by `base.html` and `base_mobile.html`: `title`, `head`, `content`.
The tab bar macro is `property_tabs(property, active)` in `_macros.html`, where `active` is one
of `overview`, `applications`, `evaluation`, `schedule`, `contract`, `conversations`.

### Landlord pages (extend `base.html`)

| Route | Template | Route unit | Template unit | Context |
|---|---|---|---|---|
| `GET /` | `dashboard.html` | B1 | C2 | `properties` (rows + `stats`), `upcoming_viewings`, `activity` (latest landlord notifications) |
| `GET /properties/new`, `GET /properties/<id>/edit` | `property_form.html` | B1 | C2 | `property` (Row or None) |
| `GET /properties/<id>` | `property.html` | B1 | C2 | `property`, `stats`, `public_link`, `copy_messages` |
| `GET /properties/<id>/applications` | `applications.html` | B2 | C3 | `property`, `applications` |
| `GET /applications/<id>` | `application.html` | B2 | C3 | `application`, `property`, `demo_files`, `conversation` (Row or None) |
| `GET /properties/<id>/evaluation` | `evaluation.html` | B3 | C3 | `property`, `eligible_count`, `remaining`, `result` (EvaluationResult or None), `applications_by_id` |
| `GET /properties/<id>/schedule` | `schedule.html` | B4 | C4 | `property`, `slots` (from `list_slots`) |
| `GET /properties/<id>/contract` | `contract.html` | B5 | C4 | `property`, `attended`, `finalist` (Row or None), `contract_files` |
| `GET /properties/<id>/conversations` | `conversations.html` | A5 | C6 | `property`, `conversations` |
| `GET /conversations/<id>` | `conversation.html` | A5 | C6 | `conversation`, `property`, `messages`, `application` (Row or None) |
| `GET /inbox` | `inbox.html` | B7 | C7 | `notifications` (rows + `recipient_name`) |
| `GET /demo` | `demo.html` | B7 | C7 | `applications` (all, with property title), `selected_token` (from `?as=`) |

`property.html`, `applications.html`, `evaluation.html`, `schedule.html`, `contract.html` and
`conversations.html` share one tab bar, provided as a macro by C1: Overview · Applications ·
Evaluation · Schedule · Contract · Conversations.

`demo.html` shows the landlord app in a wide `<iframe src="/">` and the applicant page in a
phone-sized `<iframe src="/a/<selected_token>">`, with a "view as" form (`GET /demo?as=<token>`).

| Form | Fields | Unit |
|---|---|---|
| `POST /properties` , `POST /properties/<id>` | `title`, `address`, `city`, `rental_type`, `rent_eur`, `description`, `facts`, `required_document`, `eval_mode`, `invite_limit`, `reply_mode`, `listing_ref` | B1 |
| `POST /properties/<id>/applications` (phone enquiry) | `name`, `email`, `phone`, `preferences`, `availability` (repeated) | B2 |
| `POST /applications/<id>/document/request` | — | B2 |
| `POST /applications/<id>/document/approve` | — | B2 |
| `POST /applications/<id>/document/correction` | `note` | B2 |
| `POST /applications/<id>/calendar-access` | — | B2 |
| `POST /properties/<id>/evaluation` (run) | — re-renders `evaluation.html` with `result` | B3 |
| `POST /properties/<id>/evaluation/invite` | `application_ids` (repeated) | B3 |
| `POST /properties/<id>/slots` | `date` (YYYY-MM-DD), `time` (HH:MM), `duration_min` | B4 |
| `POST /slots/<id>/delete` | — | B4 |
| `POST /slots/<id>/cancel` | — | B4 |
| `POST /slots/<id>/attendance` | `value` (`attended` or `absent`) | B5 |
| `POST /properties/<id>/finalist` | `application_id` | B5 |
| `POST /properties/<id>/contract/status` | `status` (`pending` or `sent`) | B5 |
| `POST /properties/<id>/contract/sign` | `file_name` | B5 |
| `POST /messages/<id>/approve` | `body` (optional edited text) | A5 |
| `POST /messages/<id>/discard` | — | A5 |
| `POST /conversations/<id>/reply` (manual reply) | `body` | A5 |
| `POST /worker/pause` | `paused` (`0` or `1`) | A5 |
| `POST /inbox/read-all` | — | B7 |
| `POST /demo/clock` | `minutes` | B7 |
| `POST /demo/reset` | — | B7 |

### Applicant pages (extend `base_mobile.html`)

| Route | Template | Route unit | Template unit | Context |
|---|---|---|---|---|
| `GET /apply/<property_id>` | `apply.html` | B6 | C5 | `property` |
| `GET /a/<token>` | `applicant.html` | B6 | C5 | `application`, `property`, `needs_details` (bool), `demo_files`, `slots` (from `slots_for_applicant`), `notifications`, `is_finalist`, `contract_status` |

| Form | Fields |
|---|---|
| `POST /apply/<property_id>` → redirects to `/a/<token>` | `name`, `email`, `phone`, `preferences`, `availability` (repeated) |
| `POST /a/<token>/details` | `name`, `email`, `phone`, `preferences`, `availability` (repeated) |
| `POST /a/<token>/document` | `file_name` |
| `POST /a/<token>/book` | `slot_id` |
| `POST /a/<token>/cancel` | `slot_id` |
| `POST /a/<token>/waitlist/join` | `slot_id` |
| `POST /a/<token>/waitlist/leave` | `slot_id` |
| `POST /a/<token>/offer/accept` | `slot_id` |
| `POST /a/<token>/offer/decline` | `slot_id` |

All handled by B6. After `POST /a/<token>/document` commits, the route calls
`doc_summary.summarize_for_landlord(application_id)`. `application.html` (landlord side) shows
`application.doc_summary` with an "AI check — review the document yourself" label.

`applicant.html` shows only what the status allows: the details form while
`needs_details`, the document step, then the calendar once `application.calendar_access` is 1.
An active offer is shown first, with its deadline.

### Mock portal (A1 routes, C6 templates; own look, does not extend `base.html`)

| Route | Template | Context / fields |
|---|---|---|
| `GET /mock/inbox` | `mock_inbox.html` | `threads` (rows + `last_message`, `unanswered`) |
| `GET /mock/inbox/<thread_id>` | `mock_thread.html` | `thread`, `messages` |
| `POST /mock/inbox/<thread_id>/send` | — | `body` (the landlord's reply; this is the form the browser agent fills) |
| `GET /mock/candidate` | `mock_candidate.html` | `threads` |
| `POST /mock/candidate/send` | — | `thread_id` (empty = new thread), `contact_name`, `body` |

Keep the mock portal's HTML simple and labelled (clear headings, one text box, one "Send"
button), so a browser agent can use it reliably.

## 10. Seed data — B7

`seed.run(conn, now)` must make both demo moments work straight after a reset. Dates are
relative to `now`.

- **Property 1** — residential, Madrid, `eval_mode='assisted'`, `reply_mode='automatic'`,
  `invite_limit=3`, with `facts` filled in. Six applications: one `new`, one `docs_requested`,
  one `docs_uploaded`, three `docs_approved` with different availability, two of them tied on
  score so the tie-break shows. Three free slots.
- **Property 2** — temporary, Valencia, `eval_mode='automatic'`, `reply_mode='assisted'`,
  `invite_limit=5`. Three applicants already `invited`: X has a slot tomorrow, Y then Z are on
  its waiting list. Four more `docs_approved`, so an automatic run invites two and leaves two.
- **Mock portal** — three unanswered threads for property 1: a first contact, a question the
  facts answer, and a question they do not.
- Names are fictional, emails end in `@example.com`, phones look like `600 000 001`.
- `scripts/make_demo_pdfs.py` writes `payslip-demo.pdf`, `enrolment-demo.pdf` and
  `signed-contract-demo.pdf` to `housia/static/demo/`, each marked "FICTIONAL DOCUMENT — HOUSIA
  DEMO". The PDFs are committed. Each contains selectable text with invented personal data
  (a name matching a seeded applicant, a DNI-style number, an IBAN, an address), so the masking
  can be shown and tested.

## 11. Configuration — `housia/config.py` (S0), read from the environment

| Variable | Default | Meaning |
|---|---|---|
| `HOUSIA_DB` | `instance/housia.db` | SQLite file |
| `PORT` | `5000` | Web port |
| `BASE_URL` | `http://localhost:5000` | Used in links sent to candidates |
| `CHANNEL` | `mock` | `mock`, `idealista` or `badi` |
| `DEFAULT_PROPERTY_ID` | `1` | Property for messages with no matching `listing_ref` |
| `WORKER_INTERVAL_SEC` | `20` | Pause between worker loops |
| `REPLY_ENGINE` | `template` | `template` or `llm` |
| `LLM_PROVIDER` | `openai` | Used by `housia/llm.py` |
| `REPLY_MODEL` | — | OpenAI model for replies and document checks |
| `BROWSER_MODEL` | — | OpenAI model that drives the browser |
| `SEND_ALLOWLIST` | empty | Comma list of contact names or conversation ids HOUSIA may reply to on a real portal. Empty = send nothing there. |
| `CHROME_PROFILE_DIR` | `~/housia-profile` | Profile that holds the portal login |
| `IDEALISTA_INBOX_URL` | `http://localhost:5000/mock/inbox` | Set to the real inbox URL after the probe |
| `BROWSER_ALLOWED_DOMAINS` | `localhost` | Comma list; add the portal's domain for real runs |
| `OPENAI_API_KEY` | — | The team's OpenAI key |

Secrets go in `.env` (git-ignored). `.env.example` lists the names only.

## 12. Done checklist for a unit

- [ ] Only the unit's files changed (`git diff --stat origin/main`).
- [ ] Signatures, routes, form fields and template variables match this document.
- [ ] The unit's tests pass; the full `uv run pytest` run is not worse than on `main`.
- [ ] `uv run python run.py` starts and the unit's pages load after `POST /demo/reset`.
- [ ] No secrets, no real personal data, no database file committed.
- [ ] Anything the contract got wrong is reported to the main backend person, not patched locally.

Tests each unit must include at least:

| Unit | Must prove |
|---|---|
| A1 | a fetched message is not returned twice; a sent reply appears in the thread |
| A2 | with a non-local inbox URL and an empty allowlist, `send_reply` raises and opens no browser |
| A3 | a message recorded twice yields one row; a second reply to the same incoming message is rejected; assisted mode saves a draft and sends nothing; a flagged reply is never sent; a failed send is not retried |
| A4 | first-contact reply contains the link and the required document; an unknown question sets `needs_landlord`; `llm` failure falls back to `template` |
| A7 | a text with a name, email, phone, DNI, NIE and IBAN comes out with none of them; `unmask(mask(x))` returns `x`; the same value gets the same placeholder; `complete` sends only masked text to the model (checked with a fake model) and returns unmasked text; `assert_clean` raises when a known value survives |
| A8 | the model receives no real value from the seeded PDF (fake model); the saved summary contains the real name again; a model error still leaves a summary and raises nothing |
| B2 | every allowed transition works and the others raise `DomainError` |
| B3 | ranking by score; tie broken by `created_at`; assisted changes nothing; automatic stops at `invite_limit`; `invite` over the limit fails |
| B4 | double booking fails and leaves the state unchanged; a cancellation creates exactly one offer and one applicant notification; deadline is `min(now + 30 min, starts_at)`; decline and expiry pass the offer on; an empty waitlist frees the slot |
| B5 | finalist must have attended; contract cannot be signed without a file; others are closed on signing |
| B7 | after `seed.run`, cancelling X's booking offers the slot to Y, and `tick` 31 minutes later offers it to Z |
