# HOUSIA

HOUSIA is a rental workflow prototype for landlords. It brings enquiries, applications,
document review, viewing bookings, and contract decisions into one small Flask app. A mock
portal makes the full demo usable without a third-party account.

**Start here:** [the project guide](PLAN.md) describes the product plan, and [DESIGN.md](DESIGN.md)
documents the technical design.

## Quick start

You need Python 3.12 or later and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync
```

Create a fresh demo database with sample properties, applicants, viewing slots, and mock
messages, then start the app:

```bash
HOUSIA_DB=instance/demo.db uv run python -c "from housia import db; db.reset_db()"
HOUSIA_DB=instance/demo.db uv run python run.py
```

Open [http://localhost:5000/guide](http://localhost:5000/guide) for a guided walkthrough, or
[http://localhost:5000/](http://localhost:5000/) for the dashboard. The reset command replaces
all data in the database named by `HOUSIA_DB`; the example above uses its own `instance/demo.db`
file. The app uses SQLite and creates the database schema automatically, but a new database
does not contain the sample data until it is reset.

To use the default database and settings instead, copy the example configuration first:

```bash
cp .env.example .env
uv run python run.py
```

The mock channel and template reply engine are the defaults. `.env` is optional for a local run.

## Try the demo

The seeded data supports two walkthroughs:

1. **Mock portal:** open `/mock/inbox`, send or inspect an enquiry, then run the worker to see
   HOUSIA process replies.
2. **Rental workflow:** from the dashboard, open a property to review applicants, documents,
   evaluation, viewings, attendance, and the contract. Applicant links let a candidate submit
   details, share a demo document, and manage a viewing.

Use the guide's demo clock to move simulated time forward, and **Reset demo** to reload the seed
data. Resetting replaces the selected database contents.

Run the worker in a second terminal, pointing it at the same database as the web app:

```bash
HOUSIA_DB=instance/demo.db uv run python -m housia.worker
```

Use `--once` to process a single pass and exit:

```bash
HOUSIA_DB=instance/demo.db uv run python -m housia.worker --once
```

## What the app includes

- **Rental pipeline:** properties, public application links, applicant records, document
  requests, assisted or automatic applicant evaluation, viewing slots, a waiting list, a final
  candidate, and a contract status.
- **Mock portal and worker:** the local portal simulates incoming enquiries. The worker reads
  messages, prepares replies, and handles sending according to each property's reply mode.
- **Idealista browser channel:** an experimental browser-use integration can read and reply to
  an Idealista inbox. It requires a manually signed-in Chrome profile, an OpenAI API key, and a
  browser model. Sending to a non-local portal is restricted by `SEND_ALLOWLIST`.
- **Imported-enquiry workspace:** import a CSV from Idealista, Fotocasa, or WhatsApp; review
  readable PDF payslips; prepare a decision and reply; and schedule viewings. Replies are copied
  to the original channel by the landlord—the workspace does not send them through provider
  APIs.
- **Private demo options:** the public demo script supports an optional read-only judge login
  and isolated guest copies of the demo.

The core applicant workflow uses bundled demo documents. The imported-enquiry workspace accepts
PDF payslips and extracts labelled income locally; it does not authenticate documents or run
OCR. Any screening result is for the landlord to review.

## Configuration

Copy `.env.example` to `.env` to configure the app. These are the settings most people need:

| Variable | Default | Purpose |
| --- | --- | --- |
| `HOUSIA_DB` | `instance/housia.db` | SQLite database path, relative to the repository root unless absolute. |
| `PORT` | `5000` | Local web server port. |
| `BASE_URL` | `http://localhost:5000` | Base URL used to create applicant links. |
| `CHANNEL` | `mock` | Worker channel. The public demo only allows `mock`. |
| `REPLY_ENGINE` | `template` | Reply generation mode; `llm` requires an OpenAI API key. |
| `OPENAI_API_KEY` | unset | Used by model-backed replies, document summaries, and browser automation. |
| `REPLY_MODEL` | unset | Model for generated replies and optional workspace screening notes. |
| `BROWSER_MODEL` | unset | Model that drives the Idealista browser integration. |
| `IDEALISTA_INBOX_URL` | local mock inbox | Inbox URL opened by the Idealista integration. |
| `SEND_ALLOWLIST` | empty | Contacts or conversation IDs allowed for non-local Idealista sending. |
| `SECRET_KEY` | development key | Set a unique secret before enabling owner sign-in or guest demos. |
| `OWNER_PASSWORD` | unset | Enables owner sign-in (username `owner`). Required by the public demo script. |
| `JUDGE_PASSWORD` | unset | Optional read-only judge sign-in (username `judge`); must differ from owner password. |
| `WORKSPACE_AI_NOTES` | `0` | Set to `1` to enable optional AI screening explanations. |
| `GUEST_LINK_CODE` | unset | Enables private guest demos when used with the public demo script. |

Other options, including worker timing, Chrome profile, browser domain limits, and sandbox
capacity, are listed in [.env.example](.env.example).

### Idealista setup

The normal local demo needs no portal login. To try the experimental Idealista channel, configure
`CHANNEL=idealista`, set `IDEALISTA_INBOX_URL`, `BROWSER_MODEL`, and `OPENAI_API_KEY`, and log in
manually to the dedicated browser profile:

```bash
uv run python scripts/idealista_probe.py --login
uv run python scripts/idealista_probe.py
```

The probe checks the saved login and sends nothing. Portal automation can be blocked by the site
and may be restricted by its terms. Use a test account and an explicit `SEND_ALLOWLIST`; the
default allowlist is empty.

## Optional public demo

[`scripts/demo_public.sh`](scripts/demo_public.sh) runs the app and, by default, the worker behind
a temporary Cloudflare HTTPS tunnel. Install `cloudflared`, set `OWNER_PASSWORD` in `.env`, then
run:

```bash
scripts/demo_public.sh              # app, tunnel, and worker
scripts/demo_public.sh --no-worker  # app and tunnel only
```

The script uses the mock portal and a separate `instance/demo.db` by default. It prints a public
URL; press **Ctrl-C** to stop the processes. Applicant pages are public to anyone with their
private link. Owner pages require the `owner` username and `OWNER_PASSWORD`. Set a strong,
unique `SECRET_KEY` for a stable deployment. A distinct `JUDGE_PASSWORD` enables read-only judge
access. Set `GUEST_LINK_CODE` to print a guest link that gives each visitor a separate copy of
the demo database. Guest copies are temporary and their capacity is configurable with
`SANDBOX_MAX`.

## Imported-enquiry workspace details

On a property page, the workspace has **Import**, **Screen**, **Reply**, and **Viewings** steps.
Download the CSV template in the app; the required columns are `name,thread_ref`. Import one
channel at a time. WhatsApp references must be international phone numbers, such as
`+34600123456`. Re-importing an existing thread for the same property and channel is skipped.

Screening checks for labelled net pay in readable English or Spanish payslip PDFs. It flags
missing, ambiguous, or unreadable evidence for review and does not automatically reject anyone.
The uploaded PDF is processed for extraction and is not retained; an extracted income amount is
kept until a decision is recorded. Optional AI explanations send only the screening result
category to the configured model, not the document, income, or identity. The landlord copies the
reply into the original Idealista, Fotocasa, or WhatsApp conversation and marks it sent in HOUSIA.
Viewing times use the app server's local timezone; this flow does not sync Google Calendar.

## Development

Run the test suite with:

```bash
uv run pytest
```

Useful project areas:

| Path | Contents |
| --- | --- |
| `housia/services/` | Rental, scheduling, conversation, and screening rules. |
| `housia/web/` | Flask routes. |
| `housia/templates/` and `housia/static/` | Server-rendered pages and styles. |
| `housia/channels/` | Mock and portal channel integrations. |
| `tests/` | Automated tests. |
| `PLAN.md` | Product scope and milestones. |
| `DESIGN.md` | Technical contracts and implementation details. |

## Data and security

HOUSIA is a single-owner prototype, not a hosted multi-tenant service. Keep real applicant data
out of the demo, protect the SQLite file and its backups, and use HTTPS with a strong secret and
owner password before sharing applicant links. Applicant URLs act as private bearer links; avoid
sharing or logging them. Define a data-retention policy before processing real applications.
