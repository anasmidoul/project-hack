CREATE TABLE IF NOT EXISTS screening_briefs (
    property_id INTEGER PRIMARY KEY REFERENCES properties(id) ON DELETE CASCADE,
    min_net_eur INTEGER NOT NULL DEFAULT 0 CHECK (min_net_eur >= 0)
);

CREATE TABLE IF NOT EXISTS imported_enquiries (
    application_id INTEGER PRIMARY KEY REFERENCES applications(id) ON DELETE CASCADE,
    property_id INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    channel TEXT NOT NULL CHECK (channel IN ('idealista', 'fotocasa', 'whatsapp')),
    thread_ref TEXT NOT NULL,
    document_received INTEGER NOT NULL DEFAULT 0,
    payslip_detected INTEGER NOT NULL DEFAULT 0,
    net_pay_cents INTEGER,
    decision TEXT CHECK (decision IN ('invite', 'decline')),
    decision_sent_at TEXT,
    UNIQUE (property_id, channel, thread_ref)
);
