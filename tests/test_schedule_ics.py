from housia import db


def _seed(title="Sunny flat, with terrace"):
    with db.tx() as conn:
        conn.execute(
            "INSERT INTO properties (id,title,address,city,rental_type,rent_eur,required_document,created_at) "
            "VALUES (1,?,?,?,?,?,?,?)",
            (title, "Calle Mayor 1", "Madrid", "residential", 900, "Payslip", "2026-11-01T10:00:00"))
        conn.execute(
            "INSERT INTO applications (id,property_id,token,name,source,created_at) "
            "VALUES (1,1,'tok1','Ana Ruiz','link','2026-11-02T10:00:00')")
        conn.execute("INSERT INTO slots (id,property_id,starts_at,duration_min,booked_application_id) "
                     "VALUES (1,1,'2026-11-25T10:00:00',30,1)")
        conn.execute("INSERT INTO slots (id,property_id,starts_at,duration_min) "
                     "VALUES (2,1,'2026-11-26T17:30:00',45)")


def _unfold(text):
    return text.replace("\r\n ", "")


def test_booked_and_free_slot_events(client):
    _seed(title="Sunny flat")
    resp = client.get("/properties/1/schedule.ics")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "text/calendar; charset=utf-8"
    assert resp.headers["Content-Disposition"] == 'attachment; filename="viewings-property-1.ics"'
    body = _unfold(resp.get_data(as_text=True))
    assert body.count("BEGIN:VEVENT") == 2
    assert "UID:slot-1@housia" in body and "UID:slot-2@housia" in body
    assert "DTSTART:20261125T100000\r\n" in body and "DTEND:20261125T103000\r\n" in body
    assert "DTSTART:20261126T173000\r\n" in body and "DTEND:20261126T181500\r\n" in body
    assert "SUMMARY:Viewing: Sunny flat — Ana Ruiz\r\n" in body
    assert "SUMMARY:Viewing slot (free): Sunny flat\r\n" in body


def test_escaping_and_crlf(client):
    _seed()
    raw = client.get("/properties/1/schedule.ics").get_data(as_text=True)
    assert "Sunny flat\\, with terrace" in _unfold(raw)
    assert raw.endswith("END:VCALENDAR\r\n")
    assert raw.replace("\r\n", "").count("\n") == 0
    assert all(len(line.encode()) <= 75 for line in raw.split("\r\n"))


def test_unknown_property_is_404(client):
    assert client.get("/properties/999/schedule.ics").status_code == 404
