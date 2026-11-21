"""Owner workflow for imported portal leads; original channel is never changed."""

import csv
import io
import re
import secrets
from decimal import Decimal

from housia import config, core, llm

CHANNELS = {
    'idealista': ('Idealista', 'https://www.idealista.com/'),
    'fotocasa': ('Fotocasa', 'https://www.fotocasa.es/'),
    'whatsapp': ('WhatsApp', 'https://web.whatsapp.com/'),
}
INCOME_LABEL = re.compile(
    r'^\s*(?:net pay|take-home pay|net amount paid|l[ií]quido a percibir|neto a percibir)'
    r'\s*[:\-]?\s*(?P<amount>(?:€\s*)?[0-9][0-9., ]{0,16}(?:\s*(?:€|EUR))?)\s*$',
    re.I | re.M,
)
PAYSLIP = re.compile(r'\b(?:payslip|pay\s+slip|pay\s+statement|n[oó]mina|recibo de salarios)\b', re.I)


def read_csv(upload, channel):
    if not upload or not upload.filename:
        raise core.DomainError('Choose a CSV file to import.')
    content = upload.stream.read(256_001)
    if len(content) > 256_000:
        raise core.DomainError('Keep the CSV under 256 KB (up to 500 enquiries).')
    try:
        text = content.decode('utf-8-sig')
        header = text.splitlines()[0] if text.strip() else ''
        reader = csv.DictReader(io.StringIO(text), delimiter=';' if ';' in header else ',', strict=True)
        columns = [col.strip().lower() for col in (reader.fieldnames or [])]
        if len(columns) != len(set(columns)) or not {'name', 'thread_ref'} <= set(columns):
            raise core.DomainError('The CSV needs name and thread_ref columns. Download the template for an example.')
        reader.fieldnames = columns
        rows = []
        for row in reader:
            name = (row.get('name') or '').strip()
            ref = (row.get('thread_ref') or '').strip()
            if not name or not ref or len(name) > 120 or len(ref) > 250 or None in row:
                raise core.DomainError(f'Check line {reader.line_num}: include a name and original thread reference.')
            if channel == 'whatsapp':
                ref = re.sub(r'[\s()\-]', '', ref)
                if not re.fullmatch(r'\+[1-9][0-9]{6,14}', ref):
                    raise core.DomainError(f'Check line {reader.line_num}: WhatsApp numbers must include the country code (for example +34600123456).')
            rows.append((name, ref))
            if len(rows) > 500:
                raise core.DomainError('Import no more than 500 enquiries at a time.')
        if not rows:
            raise core.DomainError('This CSV does not contain any enquiries.')
        return rows
    except (UnicodeError, csv.Error):
        raise core.DomainError('The file could not be read. Save it as a UTF-8 CSV and try again.') from None


def import_rows(conn, property_id, channel, rows):
    existing = {row[0] for row in conn.execute(
        'SELECT thread_ref FROM imported_enquiries WHERE property_id = ? AND channel = ?',
        (property_id, channel),
    )}
    count = 0
    now = core.now(conn).isoformat()
    for name, ref in rows:
        if ref in existing:
            continue
        app_id = conn.execute(
            'INSERT INTO applications (property_id, token, name, source, created_at, status) '
            "VALUES (?, ?, ?, ?, ?, 'docs_requested')",
            (property_id, secrets.token_urlsafe(32), name, channel, now),
        ).lastrowid
        conn.execute('INSERT INTO imported_enquiries (application_id, property_id, channel, thread_ref) VALUES (?, ?, ?, ?)',
                     (app_id, property_id, channel, ref))
        existing.add(ref)
        count += 1
    return count


def enquiries(conn, property_id):
    return conn.execute(
        'SELECT a.*, e.channel, e.thread_ref, e.document_received, e.payslip_detected, '
        'e.net_pay_cents, e.decision, e.decision_sent_at '
        'FROM imported_enquiries e JOIN applications a ON a.id = e.application_id '
        'WHERE e.property_id = ? ORDER BY a.id DESC', (property_id,),
    ).fetchall()


def minimum_income(conn, property_id):
    row = conn.execute('SELECT min_net_eur FROM screening_briefs WHERE property_id = ?', (property_id,)).fetchone()
    return row[0] if row else 0


def parse_net_pay(amount):
    amount = amount.replace('€', '').replace('EUR', '').replace(' ', '')
    # Require cents as printed on payslips; a lone separator with three digits is ambiguous.
    if re.fullmatch(r'(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2}', amount):
        amount = amount.replace('.', '').replace(',', '.')
    elif re.fullmatch(r'(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}', amount):
        amount = amount.replace(',', '')
    else:
        return None
    return int(Decimal(amount) * 100)


def read_payslip(upload):
    from pypdf import PdfReader

    if not upload or not upload.filename:
        raise core.DomainError('Choose a payslip PDF.')
    data = upload.stream.read(2_000_001)
    if len(data) > 2_000_000 or not data.startswith(b'%PDF-'):
        raise core.DomainError('Upload a PDF under 2 MB.')
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted or len(reader.pages) > 8:
            raise core.DomainError('Use an unlocked PDF with at most 8 pages.')
        text = '\n'.join(page.extract_text() or '' for page in reader.pages)
    except core.DomainError:
        raise
    except Exception:
        raise core.DomainError('This PDF could not be read. Try a new PDF from your payroll provider.') from None
    is_payslip = bool(PAYSLIP.search(text))
    amounts = {parse_net_pay(match.group('amount').strip().upper()) for match in INCOME_LABEL.finditer(text)}
    return is_payslip, amounts.pop() if is_payslip and len(amounts) == 1 else None


def screening(row, minimum):
    if not row['document_received']:
        return 'missing', 'Waiting for a payslip'
    if not row['payslip_detected']:
        return 'review', 'Could not identify a payslip'
    if row['net_pay_cents'] is None:
        return 'review', 'Monthly net pay could not be confirmed'
    if row['net_pay_cents'] < minimum * 100:
        return 'below', 'Below your net income minimum'
    return 'match', 'Matches your screening brief'


def ai_note(state):
    """Optional evidence explanation. Only a fixed, non-identifying category leaves the server."""
    if not config.WORKSPACE_AI_NOTES or not config.REPLY_MODEL or not config.OPENAI_API_KEY:
        return None
    try:
        return llm.complete(
            'Explain this payslip screening outcome to a landlord in one short English sentence. '
            'Do not make a decision, assume anything about the person, or claim the document is authentic.',
            f'Screening category: {state}.',
        )[:300]
    except llm.LLMError:
        return None


def drafts(row, title):
    name = row['name'].split()[0]
    upload = f"{config.BASE_URL.rstrip('/')}/viewing/{row['token']}"
    return {
        'request': f'Hi {name}, thanks for your interest in {title}. Could you upload your latest monthly payslip here? {upload}',
        'invite': f'Hi {name}, thanks for applying for {title}. I’d like to invite you to a viewing. Pick a time that works for you here: {upload}',
        'decline': f'Hi {name}, thanks for your interest in {title}. I won’t be moving forward with your application. I appreciate your time and wish you all the best with your search.',
    }
