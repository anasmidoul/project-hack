import json

from housia import config, db


def test_reset_loads_extra_property_and_enquiries(client, tmp_path, monkeypatch):
    extra = tmp_path / "extra.json"
    extra.write_text(json.dumps({
        "property": {"title": "Extra flat", "address": "Calle Falsa 1", "city": "Madrid", "rental_type": "residential",
                     "rent_eur": 900, "required_document": "Latest payslip", "listing_ref": "X-1"},
        "threads": [{"contact_name": "Test Person", "body": "Is it still available?"}, {"contact_name": "Empty", "body": " "}],
    }))
    monkeypatch.setattr(config, "DEMO_EXTRA_FILE", str(extra))
    client.post("/demo/reset")
    with db.tx() as conn:
        prop = conn.execute("SELECT * FROM properties WHERE listing_ref = 'X-1'").fetchone()
        threads = conn.execute("SELECT * FROM mock_threads WHERE listing_ref = 'X-1'").fetchall()
        assert prop["title"] == "Extra flat" and prop["rent_eur"] == 900
        assert [t["contact_name"] for t in threads] == ["Test Person"]
        message = conn.execute("SELECT sender, body FROM mock_messages WHERE thread_id = ?", (threads[0]["id"],)).fetchone()
        assert (message["sender"], message["body"]) == ("candidate", "Is it still available?")


def test_reset_without_the_file_adds_nothing(client):
    client.post("/demo/reset")
    with db.tx() as conn:
        assert conn.execute("SELECT COUNT(*) FROM properties").fetchone()[0] == 2
