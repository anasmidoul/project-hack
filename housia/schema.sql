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
