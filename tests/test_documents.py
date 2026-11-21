"""Unit B2 tests: document request, upload, approve and correction."""
import pytest

from housia import core
from housia.services import documents


def _app(conn, t0):
    conn.execute("INSERT INTO properties (id,title,address,city,rental_type,rent_eur,required_document,created_at) "
                 "VALUES (1,'P','A','C','residential',900,'Payslip',?)", (t0.isoformat(),))
    return conn.execute("INSERT INTO applications (property_id,token,name,source,created_at) "
                        "VALUES (1,'tok','Ana','link',?)", (t0.isoformat(),)).lastrowid


def _status(conn, app_id):
    return conn.execute("SELECT status FROM applications WHERE id=?", (app_id,)).fetchone()[0]


def test_request_upload_approve(conn, t0):
    app_id = _app(conn, t0)
    assert _status(conn, app_id) == "new"
    documents.request_document(conn, app_id, t0)
    assert _status(conn, app_id) == "docs_requested"
    documents.upload_document(conn, app_id, documents.demo_files()[0], t0)
    assert _status(conn, app_id) == "docs_uploaded"
    documents.approve_document(conn, app_id, t0)
    assert _status(conn, app_id) == "docs_approved"


def test_correction_then_new_upload(conn, t0):
    app_id = _app(conn, t0)
    documents.request_document(conn, app_id, t0)
    documents.upload_document(conn, app_id, documents.demo_files()[0], t0)
    documents.request_correction(conn, app_id, "Too blurry", t0)
    row = conn.execute("SELECT status,doc_note FROM applications WHERE id=?", (app_id,)).fetchone()
    assert tuple(row) == ("docs_correction", "Too blurry")
    documents.upload_document(conn, app_id, documents.demo_files()[0], t0)
    assert _status(conn, app_id) == "docs_uploaded"


def test_disallowed_moves_raise(conn, t0):
    app_id = _app(conn, t0)
    with pytest.raises(core.DomainError):
        documents.approve_document(conn, app_id, t0)
    with pytest.raises(core.DomainError):
        documents.upload_document(conn, app_id, documents.demo_files()[0], t0)
    documents.request_document(conn, app_id, t0)
    with pytest.raises(core.DomainError):
        documents.request_document(conn, app_id, t0)
    assert _status(conn, app_id) == "docs_requested"
