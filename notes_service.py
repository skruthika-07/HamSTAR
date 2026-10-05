"""
Notes generator: Mistral reads the uploaded file (text, headings, definitions), Groq writes the revision
notes in a fixed structure, and the result is kept with the student's account and can be downloaded as a PDF.
"""
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import ApiError
from ..core.logging import log
from ..models import Note, User
from ..schemas.ai import GeneratedNotes
from . import document_service, pdf_service
from .ai_client import ProviderError
from .groq_service import get_groq
from .mistral_service import get_mistral


def to_markdown(n: GeneratedNotes) -> str:
    """The notes in the one fixed layout, as markdown."""
    out = [f"# {n.title}", "", "## Headings & Subheadings"]
    for h in n.outline:
        out.append(f"- {h.heading}")
        out += [f"  - {s}" for s in h.subheadings]
    out += ["", "### Definitions", *[f"- **{d.term}**: {d.definition}" for d in n.definitions]]
    out += ["", "### Summary", n.summary]
    out += ["", "### Must-Know Keywords", *[f"- **{k.keyword}**: {k.meaning}" for k in n.keywords]]
    out += ["", "### Key Points", *[f"- {p}" for p in n.key_points]]
    out += ["", "### Topic Weightage", f"**{n.weightage.level}** — {n.weightage.reason}"]
    out += ["", "### Concept Hierarchy"]
    for c in n.hierarchy:
        out.append(f"- {c.concept}")
        for s in c.children:
            out.append(f"  - {s.concept}")
            out += [f"    - {d}" for d in s.details]
    out += ["", "### Core Concepts", *[f"- **{c.concept}**: {c.explanation}" for c in n.core_concepts]]
    out += ["", "### Potential Questions", *[f"{i}. {q}" for i, q in enumerate(n.potential_questions, 1)]]
    out += ["", "### Brief Summary", *[f"- {line}" for line in n.brief_summary]]
    return "\n".join(out).strip() + "\n"


def create(db: Session, user: User, filename: str, content_type: str | None, data: bytes) -> Note:
    ext, _ = document_service.validate(filename, content_type, data)
    label = document_service.safe_name(filename)
    try:
        text = document_service._read(data, ext)
    except ProviderError as e:
        raise ApiError("DOCUMENT_PROCESSING_FAILED", e.message, 422)
    except Exception:  # noqa: BLE001 - a damaged file is a failed read, not a crash
        raise ApiError("DOCUMENT_PROCESSING_FAILED", "This file is damaged and could not be opened.", 422)
    if len(text.strip()) < 40:
        raise ApiError("DOCUMENT_PROCESSING_FAILED", "There is too little readable text in this file to make notes from.", 422)

    # Mistral reads the structure; if it cannot be reached Groq works from the text alone
    structure = ""
    mistral = get_mistral()
    if mistral.configured:
        try:
            s = mistral.read_structure(text)
            structure = "\n".join([f"TITLE: {s.title}", "HEADINGS:", *[f"- {h.heading}: {', '.join(h.subheadings)}" for h in s.headings], "DEFINITIONS:", *[f"- {d.term}: {d.definition}" for d in s.definitions]])
        except ProviderError:
            log.warning("Mistral unavailable for reading a notes file's structure; Groq will work from the text")

    groq = get_groq()
    if not groq.configured:
        raise ApiError("AI_PROVIDER_ERROR", "Writing notes needs a Groq API key (GROQ_API_KEY).", 503)
    notes = groq.notes(text, structure)
    row = Note(user_id=user.id, title=notes.title[:200], file_name=label, content=notes.model_dump(), markdown=to_markdown(notes))
    db.add(row)
    db.commit()
    return row


def view(n: Note, full: bool = True) -> dict:
    out = {"id": n.id, "title": n.title, "file_name": n.file_name, "created_at": n.created_at.isoformat() if n.created_at else None, "weightage": (n.content or {}).get("weightage", {}).get("level")}
    if full:
        out.update({"content": n.content, "markdown": n.markdown})
    return out


def listing(db: Session, user: User) -> list[dict]:
    return [view(n, full=False) for n in db.scalars(select(Note).where(Note.user_id == user.id).order_by(Note.created_at.desc()))]


def own(db: Session, user: User, note_id: str) -> Note:
    n = db.get(Note, note_id)
    if not n or n.user_id != user.id:
        raise ApiError("NOTE_NOT_FOUND", "Those notes were not found.", 404)
    return n


# ───────────────────────── PDF ─────────────────────────


def pdf_name(n: Note) -> str:
    """HamSTAR_Notes_<Topic>.pdf, in characters every browser and file system accepts."""
    topic = re.sub(r"[^A-Za-z0-9]+", "_", n.title).strip("_")[:60] or "Notes"
    return f"HamSTAR_Notes_{topic}.pdf"


def pdf(n: Note) -> bytes:
    """The notes as a formatted PDF (see pdf_service for the libraries used)."""
    return pdf_service.render(GeneratedNotes.model_validate(n.content), n.file_name)
