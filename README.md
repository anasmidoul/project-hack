# HOUSIA

HOUSIA is an owner workspace for rentals already listed on Idealista, Fotocasa or WhatsApp. It brings enquiries, private payslip screening, same-channel replies and viewing appointments into one English-language interface.

## Run locally

```bash
uv sync
cp .env.example .env      # optional for local use
uv run python run.py      # http://localhost:5000
uv run pytest
```

## Owner workflow

1. **Import.** Add your existing listing to HOUSIA. Choose Idealista, Fotocasa or WhatsApp and upload a UTF-8 CSV using the downloadable template. Use `name,thread_ref` as the header. For Idealista and Fotocasa, `thread_ref` is the original conversation reference; for WhatsApp, use an international phone number such as `+34600123456`. Import one channel at a time. Re-importing the same thread for the same property and channel does not create a duplicate. The workspace does not fetch contacts automatically or import native WhatsApp chat-text archives.
2. **Screen.** Set the minimum monthly net income. Copy and send the payslip request from **Reply** so the applicant can upload a PDF through their private link. HOUSIA extracts labelled net pay from readable English or Spanish payslips locally, compares it with the brief and flags missing or ambiguous evidence. It does not authenticate payslips, perform OCR or automatically reject applicants. The raw PDF is not retained after the request. The extracted amount is retained in SQLite until a decision is recorded, then cleared from the record. Optional AI explanations (`WORKSPACE_AI_NOTES=1`, `REPLY_MODEL`, `OPENAI_API_KEY`) send only the result category, not the document, income or identity.
3. **Reply.** Review the screening result and choose whether to invite or decline. Copy the personalised draft, send it in the original chat, and mark it as sent. WhatsApp opens the recipient chat; for Idealista and Fotocasa, use the imported conversation reference to find the original thread. This is a manual handoff: the workspace does not send messages through provider APIs or verify delivery. Marking an invitation as sent activates the private viewing link.
4. **Viewings.** Add available times in the built-in HOUSIA agenda. Invited applicants book or cancel on their private page. The slot and the owner's in-app notification update in the same transaction. Times use the app server's local time; configure the process timezone for your rental location. There is no Google Calendar sync in this flow.

## Before sharing real applicant links

This is a single-owner prototype. Use HTTPS, set `BASE_URL` to the public HTTPS origin, and set a strong `SECRET_KEY` and `OWNER_PASSWORD` (owner sign-in username: `owner`). Do not expose the local unauthenticated configuration to the network. Treat viewing URLs as private bearer links and avoid logging their paths. Protect the SQLite database and backups, and define a retention policy for pending enquiries and extracted evidence before processing real payslips.

## Legacy demo components

`PLAN.md` and `DESIGN.md` describe the broader prototype, including an experimental worker (`uv run python -m housia.worker`), portal integrations and contract stages. The owner workspace does not require that worker and does not use it to deliver imported enquiries or decisions.
