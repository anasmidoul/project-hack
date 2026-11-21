# HOUSIA — plan

Status: plan agreed. Nothing is built yet. The technical contract is in [DESIGN.md](DESIGN.md).

## Goal

A rental platform where the landlord's side runs by itself:

1. A listing goes up on Idealista. HOUSIA reads every message it receives and answers it.
2. The answer sends the candidate to HOUSIA, where the whole process continues: application,
   documents, ranking, viewing, waiting list, final choice, contract.

The demo has two key moments:
- A message arrives on Idealista and is answered with no landlord input.
- A viewing is cancelled and the slot is offered to the next person on the waiting list.

## Decisions

| Topic | Decision |
|---|---|
| Backend | Python 3.11+, Flask, Jinja templates |
| Frontend | HTML and CSS, rendered by the server. No JavaScript framework. |
| Storage | One SQLite file |
| Language | English everywhere |
| Idealista | Browser automation with `browser-use` in the landlord's logged-in Chrome |
| AI models | OpenAI, for writing replies, checking documents and driving the browser |
| Idealista account | A real landlord account with a live listing exists. No second account for test enquiries yet. |
| Personal data and AI | Names, contact details and identity numbers are replaced with placeholders before any text goes to an AI model, and restored on our side afterwards |
| Risk | Automating Idealista breaks its terms and may be blocked. Accepted for testing. Team accounts only. |
| Data | Fake data and fake documents only |

## Scope

### Message automation (first priority)

| # | Feature |
|---|---|
| M1 | Read new messages from the Idealista inbox through the browser |
| M2 | Reply engine: writes the answer from the listing facts; flags what it cannot answer |
| M3 | Reply modes per property: **Assisted** (landlord approves each reply) and **Automatic** (sent directly) |
| M4 | Worker loop: each message handled once, replies sent through the browser |
| M5 | Landlord conversation pages: threads, drafts, approve, edit, pause |
| M6 | Mock inbox: a local page that looks like a portal chat, used for development and as the demo fallback |
| M7 | Privacy guard: personal data is masked before every AI model call |
| M8 | Document check: when a tenant uploads a document, an AI model reads the masked text and sends the landlord a short summary. The landlord still decides. |
| M9 | Badi as a second channel (last, only if everything else works) |

### Rental workflow

| # | Feature |
|---|---|
| W1 | Landlord dashboard: properties, pipeline counts, upcoming viewings, activity feed |
| W2 | Properties: create, edit, view. Residential and temporary rentals. |
| W3 | Lead generation: public link per property, ready-to-copy messages (Idealista, Fotocasa, WhatsApp), add an applicant from a phone call, public application form, status tracking |
| W4 | Documents: landlord requests a document, applicant submits a fake one, landlord approves, asks for a correction, or grants calendar access |
| W5 | Evaluation, two modes per property. Ranks applications with approved documents by declared availability, ties by submission time, with an explanation. **Assisted:** landlord chooses who to invite. **Automatic:** invites the top applicants up to the landlord's limit. Labelled "Simulation". |
| W6 | Viewings: landlord creates slots; applicants book, cancel, or join the waiting list of a taken slot. A freed slot is offered first-come-first-served, 30 minutes to accept (or until the viewing starts), then it passes on. No double bookings. |
| W7 | After the viewing: attended or absent, landlord selects the final candidate |
| W8 | Contract: Pending → Sent → Signed, with a fake signed PDF attached; application marked completed |
| W9 | Demo tools: notification inbox, demo clock (+10 / +30 minutes), reset button, seed data with two properties, split view with landlord and applicant side by side |

"Assisted" and "Automatic" exist twice and are separate settings: one for replies (M3), one for
viewing invitations (W5).

## Personal data and AI models

- **What is protected:** names, emails, phone numbers, DNI/NIE/passport numbers, IBANs,
  addresses in documents, and any other long number.
- **How:** an AI model cannot read encrypted text. So each value is swapped for a placeholder
  such as `[NAME_1]` or `[ID_1]` before the request. The list linking placeholders to real
  values stays in memory on our machine for that one call. The model's answer comes back with
  placeholders, and HOUSIA puts the real values back before the landlord reads it.
- **One gate:** all text sent to a model goes through a single function. No other code may call
  a model.
- **Two limits:**
  - The browser agent looks at the real Idealista page, so the model driving it sees names and
    messages on screen. Masking cannot apply there. Accepted for testing with team accounts;
    the later fix is a fixed-selector script that reads the page without a model.
  - A name that is not in our database and not next to a label like "Name:" is not detected.
- **Not in the hackathon:** encrypting personal data inside our own database. It is a next step
  after the hackathon (see "Later").

## Team

| Person | Lane | Work units (see DESIGN.md) |
|---|---|---|
| **Main backend** | Skeleton, message automation, privacy, merges | S0, A1–A8 |
| **Backend 2** | Rental workflow | B1–B7 |
| **Frontend** | All templates and styles | C1–C7 |

Every file has exactly one owner unit. Units are listed in DESIGN.md with their files. That is
what prevents merge conflicts and lets each person run one agent per unit.

## Order of work

| Step | What | Who |
|---|---|---|
| 0 | **Skeleton** merged to `main`: folders, database schema, shared helpers, a stub for every file. Nobody else creates files before this. | Main backend |
| 0 | **Idealista probe**: log in by hand to the landlord account, check a script can open and read the inbox. It sends nothing. Decides whether the live demo runs on real Idealista or on the mock inbox. | Main backend |
| 1 | **All units in parallel**, one branch per unit, merged to `main` as soon as its tests pass | Everyone |
| 2 | **Integration**: seed data, full walkthrough on the mock inbox, then on Idealista | Everyone |
| 3 | **Rehearsal** and fixes | Everyone |

### Real Idealista without a test account

The listing is live, so messages in the real inbox come from real people.

- On real Idealista, HOUSIA only **sends** to contacts on a team allowlist. The list starts
  empty, so nothing is sent. Every other reply stays a draft.
- Reading the real inbox shows real people's names and messages to the model that drives the
  browser. Until a second account exists, keep real-inbox runs to the probe.
- To show sending on real Idealista: create a second account, send an enquiry to the listing,
  and add that contact to the allowlist. Until then, sending is shown on the mock inbox.

## Timing

The full scope does not fit in two hours. It is 22 work units, and the slow parts are the ones
agents cannot speed up: the skeleton that everyone waits for, joining units that were built
against stubs, and the browser automation on a site we do not control. Estimate, not measured:
about four hours for three people with agents. So the work is in two blocks.

### Block 1 — first two hours: both demo moments, on the mock inbox

| Time | What |
|---|---|
| 0:00–0:20 | Skeleton merged (S0). Idealista probe, read-only (part of A2). |
| 0:20–1:20 | Units in parallel (list below) |
| 1:20–1:45 | Integration: seed, full walkthrough |
| 1:45–2:00 | Rehearsal and fixes |

| Person | Block 1 units |
|---|---|
| Main backend | S0, A1 mock channel, A3 worker, A4 reply engine, A5 conversation routes, A7 privacy guard |
| Backend 2 | B1 properties and dashboard (view only), B2 applications and documents, B4 scheduling, B6 applicant routes, B7 seed and demo tools |
| Frontend | C1 base, C2 dashboard and property, C3 applications, C4 schedule, C5 applicant, C6 conversations and mock inbox, C7 demo pages |

At the end of block 1: a message in the mock inbox is answered automatically, the applicant
follows the link, submits a document, is given calendar access by the landlord, books a
viewing, and a cancellation passes the slot down the waiting list.

### Block 2 — next two hours

| Person | Block 2 units |
|---|---|
| Main backend | A2 Idealista reading and sending, A8 document check, A6 Badi if time allows |
| Backend 2 | B3 evaluation (both modes), B5 attendance, final candidate and contract, property create and edit |
| Frontend | `evaluation.html`, `contract.html`, `property_form.html`, polish |

If only two hours exist in total, block 1 is the demo and block 2 is described as next steps.
Never cut the two key demo moments or the privacy guard (M7).

## Checks before presenting

- [ ] A new inbox message gets one reply, and only one, even if the worker restarts.
- [ ] Assisted reply mode sends nothing until the landlord approves.
- [ ] A question the listing facts do not cover is flagged for the landlord, not guessed.
- [ ] No real name, email, phone or identity number appears in any text sent to a model.
- [ ] The landlord's document summary shows the real name again.
- [ ] One applicant goes from the reply link to a signed contract.
- [ ] Assisted evaluation changes nothing until the landlord confirms.
- [ ] Automatic evaluation stops at the invitation limit.
- [ ] A cancellation notifies exactly one person on the waiting list.
- [ ] Two applicants cannot book the same slot.
- [ ] An expired offer passes to the next person.
- [ ] Reset returns the demo to its starting state.
- [ ] The whole demo runs on the mock inbox with the network off.

## Later (real pilot)

- Permission or a partner agreement with Idealista and Badi.
- **Encrypt personal data in the database** (names, contact details, document numbers, uploaded
  files), with the key kept outside the database. First step after the hackathon.
- Read and type on the portals with a fixed-selector script, so no model sees the inbox.
- Hosted database in an EU region, logins, email verification, private document storage.
- Permissions per property and application, email notices, audit log, agency workspaces.
- GDPR compliance, document retention, document requirements per rental type and region.
- The landlord decides who visits and who gets the contract; autonomous selection needs an
  impact assessment first.

## Decided later

These do not block the start.

1. The second Idealista account for test enquiries. Needed before anything is sent on real
   Idealista. Until then the send allowlist stays empty.
2. Which OpenAI models to use. They are settings (`REPLY_MODEL`, `BROWSER_MODEL`), so the choice
   changes no code. Until `REPLY_MODEL` is set, replies use the template engine.
