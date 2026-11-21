"""Unit A8 — document check for the landlord: AI summary of an uploaded document.

Contract: DESIGN.md section 7 (doc_summary.py).
"""
from __future__ import annotations


def summarize_for_landlord(application_id: int) -> None:
    """Summarize the applicant's uploaded document for the landlord.

    Rules:
    - Called by the applicant upload route (B6) AFTER its transaction has committed.
    - Opens its own short transactions: read the application and property -> no transaction
      during the model call -> write the result. (This is the one service that does not take conn.)
    - Reads the text of the uploaded file from housia/static/demo/ and asks the model, through
      llm.complete(..., known=privacy.known_values(application)): what the document is, whether
      it matches property.required_document, and what is missing or unclear.
    - Saves the answer in applications.doc_summary and sends it to the landlord as a
      notification. Because llm.complete restores the placeholders locally, the landlord reads
      real names.
    - It never decides anything. The landlord still approves or asks for a correction.
    - It never raises. On any error, or with REPLY_ENGINE=template, the summary is
      "Document received: <file>. Automatic check not available."

    Harmless stub: returns None until A8 implements it.
    """
    return None
