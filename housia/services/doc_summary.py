"""Unit A8 — document check for the landlord: AI summary of an uploaded document.

Contract: DESIGN.md section 7 (doc_summary.py).

The document text reaches the model only through `llm.complete`, which masks personal data
before the call and restores it in the answer. Nothing here prints or logs document text.
"""
from __future__ import annotations

from pathlib import Path

from housia import config, core, db, llm, privacy

_DEMO_DIR = Path(__file__).resolve().parent.parent / "static" / "demo"
_MAX_CHARS = 6000
_ALLOWED_SUFFIXES = (".pdf", ".txt")

SYSTEM_PROMPT = (
    "You help a landlord check a document that a rental applicant uploaded. "
    "You get the document the landlord asked for, the applicant's name and the text of the "
    "uploaded document. Write a short check in plain English, at most five short lines:\n"
    "1. What the document is.\n"
    "2. Whether it matches the required document.\n"
    "3. Whether the name on the document matches the applicant's name.\n"
    "4. What is missing or unclear.\n"
    "Personal data has been replaced with placeholders in square brackets, such as [NAME_1] "
    "or [ID_1]. The same placeholder always stands for the same value, so you can compare "
    "them. Copy every placeholder exactly as it is written, brackets included; never change, "
    "explain or guess it. Only describe what the document shows. Never recommend accepting or "
    "rejecting the applicant: the landlord decides."
)


def _fallback(doc_file: str) -> str:
    return f"Document received: {doc_file}. Automatic check not available."


def _resolve(doc_file: str) -> Path:
    """Path of a bare file name inside the demo folder. Raises ValueError for anything else."""
    name = (doc_file or "").strip()
    if (
        not name
        or name != Path(name).name
        or "/" in name
        or "\\" in name
        or name.startswith(".")
        or Path(name).suffix.lower() not in _ALLOWED_SUFFIXES
    ):
        raise ValueError("invalid document file name")
    base = _DEMO_DIR.resolve()
    path = (base / name).resolve()
    if path.parent != base:
        raise ValueError("document file is outside the demo folder")
    return path


def _extract_text(path: Path) -> str:
    """Text of a PDF or .txt file. Tests replace this function."""
    if path.suffix.lower() == ".txt":
        return path.read_text(encoding="utf-8", errors="replace")
    import pypdf

    reader = pypdf.PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _build_user_text(required_document: str, applicant_name: str, text: str) -> str:
    return (
        f"Required document: {required_document}\n"
        f"Applicant name: {applicant_name}\n"
        "\n"
        "Text of the uploaded document:\n"
        f"{text}"
    )


def _check(application, prop) -> str:
    """Ask the model for the check. Raises on any failure."""
    path = _resolve(application["doc_file"])
    text = (_extract_text(path) or "").strip()
    if not text:
        raise ValueError("document has no text")
    user = _build_user_text(prop["required_document"], application["name"], text[:_MAX_CHARS])
    answer = llm.complete(SYSTEM_PROMPT, user, known=privacy.known_values(application))
    answer = (answer or "").strip()
    if not answer:
        raise ValueError("empty answer")
    return answer


def summarize_for_landlord(application_id: int) -> None:
    """Summarize the applicant's uploaded document for the landlord. Never raises."""
    try:
        with db.tx() as conn:
            application = conn.execute(
                "SELECT * FROM applications WHERE id = ?", (application_id,)
            ).fetchone()
            if application is None or not application["doc_file"]:
                return
            prop = conn.execute(
                "SELECT * FROM properties WHERE id = ?", (application["property_id"],)
            ).fetchone()
            if prop is None:
                return
            application = dict(application)
            prop = dict(prop)
    except Exception:
        return

    doc_file = application["doc_file"]
    summary = _fallback(doc_file)
    if config.REPLY_ENGINE != "template":
        try:
            summary = _check(application, prop)
        except Exception:  # missing file, bad PDF, LLMError, anything else
            summary = _fallback(doc_file)

    try:
        with db.tx() as conn:
            updated = conn.execute(
                "UPDATE applications SET doc_summary = ? WHERE id = ?",
                (summary, application_id),
            ).rowcount
            if not updated:
                return
            core.notify(
                conn,
                property_id=prop["id"],
                application_id=None,
                title=f"Document check: {application['name']}",
                body=summary,
                now=core.now(conn),
            )
    except Exception:
        return
