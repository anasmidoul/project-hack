# HOUSIA

A rental platform where the landlord's side runs by itself. HOUSIA reads messages from a
portal inbox (Idealista, or a built-in mock portal), answers them, and takes each candidate
through application, documents, ranking, viewing, waiting list, final choice and contract.

- What to build and why: [PLAN.md](PLAN.md)
- Technical contract (files, schema, signatures, routes): [DESIGN.md](DESIGN.md)

## Setup

Needs [uv](https://docs.astral.sh/uv/). Python 3.12 is installed by uv.

```bash
uv sync
cp .env.example .env      # optional; edit values as needed
```

## Run the web app

```bash
uv run python run.py      # http://localhost:5000
```

Use another port and database per worktree, for example
`PORT=5004 HOUSIA_DB=instance/b4.db uv run python run.py`.

## Run the worker

The worker reads portal messages, writes replies and sends approved ones.

```bash
uv run python -m housia.worker          # loop
uv run python -m housia.worker --once   # one pass
```

The channel is set by `CHANNEL` (`mock` by default).

## Run the tests

```bash
uv run pytest
```

## Reset the demo

Open `/demo` and press "Reset", or send `POST /demo/reset`. This drops the database and loads
the seed data again.

## Public demo

Shows the app on a public https address through a free Cloudflare quick tunnel (no account),
so judges can open applicant links on their phones. Needs `cloudflared` on `PATH` (binary from
Cloudflare's GitHub releases, for example in `~/.local/bin`) and `OWNER_PASSWORD` (in `.env` or
the environment).

```bash
scripts/demo_public.sh              # tunnel + app + worker
scripts/demo_public.sh --no-worker  # tunnel + app only
```

It prints the public address. Links sent to applicants use it (`BASE_URL`). It always uses the
mock portal (`CHANNEL=mock`; any other channel is refused) and `instance/demo.db` unless
`HOUSIA_DB` is set (a missing database is seeded). Logs go to `instance/demo-*.log`. Press
Ctrl-C to stop the tunnel, the app and the worker.

Requests through the tunnel (they carry Cloudflare's forwarding headers):
- **Public:** applicant pages and their forms (`/a/<token>...`, `/apply/<id>`, `/viewing/<token>`),
  `/static/...`, the favicon.
- **Owner sign-in needed** (username `owner`, password `OWNER_PASSWORD`): everything else,
  including the dashboard, property pages, `/demo` and its reset and clock, `/inbox`,
  `/worker/pause`, the CSV exports and the whole mock portal (`/mock/...`). Without
  `OWNER_PASSWORD` these answer 403. Signed-in form posts from another site are refused.
- **Judge sign-in (optional, read-only):** set `JUDGE_PASSWORD` and sign in with username
  `judge`. The judge sees every page the owner sees (GET only) and a "Judge view · read-only"
  label; any other action (reset, clock, approving, editing, cancelling...) is refused with a
  message and changes nothing. The one exception: writing a message as a candidate in the mock
  portal (`POST /mock/candidate/send`). The judge login needs `OWNER_PASSWORD` too and is off
  when `JUDGE_PASSWORD` is empty or equal to `OWNER_PASSWORD`. The same rules apply to local
  requests that need sign-in. Nothing is stored in the session: each request is checked from
  its own credentials, so a browser signed in as judge never becomes owner without the owner
  password.

Requests made directly on this machine (no forwarding headers) behave as before.

**Private guest demos (optional).** Set `GUEST_LINK_CODE` (a long random code of letters,
digits, `-` and `_`) and the script prints a `Guest link: <public address>/guest/<code>`. Each
browser that opens it gets its own copy of the demo (a SQLite file in `instance/sandboxes/`,
`SANDBOX_DIR`) and the owner's rights inside it: approve, invite, cancel, reset, move the demo
clock, add a property. Nothing a guest does reaches other guests or the main database; their
applicant pages (`/a/<token>`, `/apply/<id>`) in the same browser use their copy too, and the
worker answers their mock portal messages. New copies start from `instance/sandbox-template.db`
(`SANDBOX_TEMPLATE`), which the script builds from the demo database at start
(`uv run python -m housia.sandbox make-template`); without a template, the main database as it
is at that moment is copied. Applicant tokens are new in every copy. At most `SANDBOX_MAX`
copies (default 150): when full, copies idle for 30 minutes are removed, otherwise the link
answers "The demo is full". Copies unused for 12 hours are deleted when the app starts. A wrong
code, an empty `GUEST_LINK_CODE` or the default `SECRET_KEY` answer 404. Owner and judge
sign-ins always use the main database, also in a browser that has a guest demo.

## Owner workspace (imported enquiries)

On each property page (steps Import, Screen, Reply, Viewings). For listings whose enquiries arrive outside HOUSIA; independent of the worker.

1. **Import.** Add your existing listing to HOUSIA. Choose Idealista, Fotocasa or WhatsApp and upload a UTF-8 CSV using the downloadable template. Use `name,thread_ref` as the header. For Idealista and Fotocasa, `thread_ref` is the original conversation reference; for WhatsApp, use an international phone number such as `+34600123456`. Import one channel at a time. Re-importing the same thread for the same property and channel does not create a duplicate. The workspace does not fetch contacts automatically or import native WhatsApp chat-text archives.
2. **Screen.** Set the minimum monthly net income. Copy and send the payslip request from **Reply** so the applicant can upload a PDF through their private link. HOUSIA extracts labelled net pay from readable English or Spanish payslips locally, compares it with the brief and flags missing or ambiguous evidence. It does not authenticate payslips, perform OCR or automatically reject applicants. The raw PDF is not retained after the request. The extracted amount is retained in SQLite until a decision is recorded, then cleared from the record. Optional AI explanations (`WORKSPACE_AI_NOTES=1`, `REPLY_MODEL`, `OPENAI_API_KEY`) send only the result category, not the document, income or identity.
3. **Reply.** Review the screening result and choose whether to invite or decline. Copy the personalised draft, send it in the original chat, and mark it as sent. WhatsApp opens the recipient chat; for Idealista and Fotocasa, use the imported conversation reference to find the original thread. This is a manual handoff: the workspace does not send messages through provider APIs or verify delivery. Marking an invitation as sent activates the private viewing link.
4. **Viewings.** Add available times in the built-in HOUSIA agenda. Invited applicants book or cancel on their private page. The slot and the owner's in-app notification update in the same transaction. Times use the app server's local time; configure the process timezone for your rental location. There is no Google Calendar sync in this flow.

### Before sharing real applicant links

This is a single-owner prototype. Use HTTPS, set `BASE_URL` to the public HTTPS origin, and set a strong `SECRET_KEY` and `OWNER_PASSWORD` (owner sign-in username: `owner`). Do not expose the local unauthenticated configuration to the network. Treat viewing URLs as private bearer links and avoid logging their paths. Protect the SQLite database and backups, and define a retention policy for pending enquiries and extracted evidence before processing real payslips.
