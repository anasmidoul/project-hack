import pytest

from housia import core, seed
from housia.services import applications, documents


def test_application_document_transitions_and_rejection(conn, t0):
    seed.run(conn, t0)
    applicant_id = applications.create_application(
        conn, 1, {"name": "Test Applicant", "email": "test@example.com", "phone": "600000099",
                 "availability": ["morning"]}, "link", t0,
    )
    documents.request_document(conn, applicant_id, t0)
    assert applications.get_application(conn, applicant_id)["status"] == "docs_requested"
    documents.upload_document(conn, applicant_id, documents.demo_files()[0], t0)
    documents.request_correction(conn, applicant_id, "Please provide a newer file.", t0)
    assert applications.get_application(conn, applicant_id)["status"] == "docs_correction"
    documents.upload_document(conn, applicant_id, documents.demo_files()[0], t0)
    documents.approve_document(conn, applicant_id, t0)
    assert applications.get_application(conn, applicant_id)["status"] == "docs_approved"
    with pytest.raises(core.DomainError):
        documents.approve_document(conn, applicant_id, t0)
