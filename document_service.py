"""Uploads: validate, store safely, read (Mistral OCR for PDFs, slides and images), and find the concepts."""
import html
import io
import re
import zipfile
from pathlib import Path

from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.errors import ApiError
from ..core.logging import log
from ..engine.bank import seed_bank
from ..models import StudyMaterial, User
from ..models.base import new_id
from . import folder_service
from .ai_client import ProviderError
from .mistral_service import get_mistral

# extension → (kind shown in the app, MIME types a browser may send for it)
ALLOWED = {
    ".pdf": ("pdf", {"application/pdf"}),
    ".pptx": ("ppt", {"application/vnd.openxmlformats-officedocument.presentationml.presentation"}),
    ".png": ("image", {"image/png"}),
    ".jpg": ("image", {"image/jpeg"}),
    ".jpeg": ("image", {"image/jpeg"}),
    ".webp": ("image", {"image/webp"}),
    ".txt": ("notes", {"text/plain"}),
    ".md": ("notes", {"text/markdown", "text/plain", "text/x-markdown"}),
    ".docx": ("notes", {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}),
}
GENERIC = {"application/octet-stream", ""}
SIGNATURES = {".pdf": b"%PDF", ".png": b"\x89PNG", ".jpg": b"\xff\xd8", ".jpeg": b"\xff\xd8", ".pptx": b"PK", ".docx": b"PK"}

# Used only when no AI is available to name the subject. Any subject is accepted; this list just helps guess.
SUBJECT_WORDS = {
    "Object-Oriented Programming": r"\boop\b|object[- ]oriented|inheritance|polymorphism|encapsulation|constructor|\bclass(es)?\b",
    "Data Structures": r"data structure|linked list|binary tree|\bstack\b|\bqueue\b|hash table|\bgraph\b|big[- ]o|sorting algorithm",
    "Computer Science": r"algorithm|operating system|database|compiler|computer network|\bcpu\b|programming|software",
    "Physics": r"physics|velocity|acceleration|newton|momentum|\bforce\b|kinetic|thermodynamic|electric|magnetic|quantum",
    "Chemistry": r"chemistry|molecule|\batom|periodic table|\bacid\b|\bbase\b|reaction|covalent|ionic|organic compound|\bmole\b",
    "Biology": r"biology|\bcell\b|photosynthesis|\bdna\b|enzyme|organism|evolution|mitosis|ecosystem|chloroplast",
    "History": r"history|\bwar\b|revolution|empire|dynasty|century|treaty|colonial|independence|civili[sz]ation",
    "Geography": r"geography|climate|continent|river|plate tectonic|latitude|longitude|population|monsoon|erosion",
    "Calculus": r"calculus|derivative|integral|differentiat|\blimit\b|integration",
    "Statistics": r"statistic|probability|standard deviation|\bmean\b|\bmedian\b|variance|regression|hypothesis test|distribution",
    "Economics": r"economics|demand|supply|inflation|\bgdp\b|market|elasticity|fiscal|monetary",
    "Mathematics": r"fraction|numerator|denominator|algebra|equation|polynomial|geometry|theorem|trigonometr|matrix",
    "English": r"grammar|\bnoun\b|\bverb\b|poem|novel|essay|literature|metaphor|comprehension",
}
GENERAL = "General"

TOPIC_WORDS = {
    "fractions": r"fraction|numerator|denominator|half|quarter|third",
    "algebra": r"algebra|equation|variable|bracket|expand|simplif|factor|polynomial|expression",
}


def safe_name(name: str) -> str:
    """The user's filename is kept only as a label: no directories, no odd characters."""
    base = Path(name or "file").name
    return re.sub(r"[^A-Za-z0-9._ -]", "_", base)[:120] or "file"


def validate(filename: str, content_type: str | None, data: bytes) -> tuple[str, str]:
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED:
        raise ApiError("INVALID_FILE_TYPE", "Upload a PDF, PowerPoint (.pptx), image, or notes file (.txt, .md, .docx).", 415)
    kind, mimes = ALLOWED[ext]
    if (content_type or "").split(";")[0].strip().lower() not in mimes | GENERIC:
        raise ApiError("INVALID_FILE_TYPE", "The file's type does not match its extension.", 415)
    limit = get_settings().max_upload_size_mb
    if len(data) > limit * 1024 * 1024:
        raise ApiError("FILE_TOO_LARGE", f"Files can be at most {limit} MB.", 413)
    if not data:
        raise ApiError("INVALID_FILE_TYPE", "The file is empty.", 415)
    sig = SIGNATURES.get(ext)
    if sig and not data.startswith(sig):
        raise ApiError("INVALID_FILE_TYPE", "The file's contents do not match its extension.", 415)
    return ext, kind


def guess_topic(text: str) -> str | None:
    """Match the material to a verified bank topic by its vocabulary, when one clearly fits."""
    counts = {t: len(re.findall(p, text, re.IGNORECASE)) for t, p in TOPIC_WORDS.items()}
    best = max(counts, key=counts.get)
    others = [c for t, c in counts.items() if t != best]
    return best if counts[best] > 0 and all(counts[best] > c for c in others) else None


def clean_subject(text: str | None) -> str | None:
    """A subject name as typed or detected: trimmed, one line, at most 80 characters. Any subject is valid."""
    text = re.sub(r"\s+", " ", (text or "")).strip(" .:-\"'")
    return text[:80] or None


def guess_subject(text: str) -> str | None:
    """Best keyword match, or None when nothing stands out. Never a reason to reject a file."""
    counts = {s: len(re.findall(p, text, re.IGNORECASE)) for s, p in SUBJECT_WORDS.items()}
    best = max(counts, key=counts.get)
    return best if counts[best] >= 2 else None


def store_and_process(db: Session, user: User, filename: str, content_type: str | None, data: bytes, topic_hint: str | None, subject_hint: str | None = None, parent_hint: str | None = None) -> StudyMaterial:
    ext, kind = validate(filename, content_type, data)
    label = safe_name(filename)

    # stored under a generated name inside the upload directory, never under a name the user chose
    root = Path(get_settings().upload_dir).resolve()
    folder = root / user.id
    folder.mkdir(parents=True, exist_ok=True)
    path = (folder / f"{new_id()}{ext}").resolve()
    if root not in path.parents:
        raise ApiError("INVALID_FILE_TYPE", "Invalid file name.", 400)
    path.write_bytes(data)

    m = StudyMaterial(user_id=user.id, title=Path(label).stem[:200], file_name=label, file_type=kind, file_path=str(path), file_size=len(data), processing_status="PENDING")
    db.add(m)
    db.flush()
    detected, ai_parent = process(m, data, ext, content_type)
    # what the student typed wins; then what the AI read; then a keyword guess; otherwise it is left for them to choose
    subject = clean_subject(subject_hint) or clean_subject(detected) or guess_subject(f"{label} {m.extracted_text[:20000]}")
    bank_topics = {t["id"]: t["name"] for t in seed_bank().topics}
    m.topic = topic_hint if topic_hint in bank_topics else guess_topic(f"{label} {m.extracted_text[:20000]}")
    # the parent folder ("Maths") and the subfolder inside it ("Fractions"); a broad subject names only the parent
    m.parent_subject, m.subject = folder_service.place(subject, parent_hint, ai_parent)
    if not m.subject and m.topic and folder_service.parent_of(bank_topics[m.topic]) == m.parent_subject:
        m.subject = bank_topics[m.topic]
    db.commit()
    return m


def _office_text(data: bytes, ext: str) -> str:
    """Text of a .docx or .pptx, read straight from the XML inside the file. Nothing in it is executed."""
    tag, parts = ("w:t", lambda n: n == "word/document.xml") if ext == ".docx" else ("a:t", lambda n: n.startswith("ppt/slides/slide") and n.endswith(".xml"))
    out = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in sorted(n for n in z.namelist() if parts(n)):
            xml = z.read(name).decode("utf-8", errors="replace")
            # one line per paragraph, with the text runs inside it joined up
            paragraphs = re.split(r"</(?:w:p|a:p)>", xml)
            lines = ["".join(html.unescape(t) for t in re.findall(rf"<{tag}(?:\s[^>]*)?>([^<]*)</{tag}>", p)) for p in paragraphs]
            out.append("\n".join(line for line in lines if line.strip()))
    return "\n\n".join(o.strip() for o in out if o.strip())


def _pdf_text(data: bytes) -> str:
    """Text layer of a PDF. Scanned PDFs have none and need OCR."""
    from pypdf import PdfReader

    try:
        return "\n\n".join((page.extract_text() or "").strip() for page in PdfReader(io.BytesIO(data)).pages).strip()
    except Exception:  # noqa: BLE001 - a damaged PDF is a failed read, not a crash
        return ""


def _read(data: bytes, ext: str) -> str:
    """
    Get the text out of an upload. Mistral OCR is preferred for PDFs and images; where the account
    cannot use it, PDFs fall back to their own text layer and images to the vision chat model.
    """
    mistral = get_mistral()
    if ext in (".txt", ".md"):
        return data.decode("utf-8", errors="replace")
    if ext in (".docx", ".pptx"):
        return _office_text(data, ext)
    mime = next(iter(ALLOWED[ext][1]))
    if ext == ".pdf":
        text = _pdf_text(data)
        if len(text) >= 40:
            return text
        if mistral.configured:
            try:
                return mistral.ocr(data, mime)
            except ProviderError:
                log.warning("Mistral OCR unavailable for a PDF with no text layer")
        if not text:
            raise ProviderError("mistral", "This PDF has no readable text layer (it looks scanned). " + ("Reading scans needs Mistral OCR, which this Mistral plan does not include." if mistral.configured else "Reading scans needs a Mistral API key (MISTRAL_API_KEY)."))
        return text
    if ALLOWED[ext][0] == "image" and mistral.configured:
        try:
            return mistral.ocr(data, mime)
        except ProviderError:
            log.warning("Mistral OCR unavailable; reading the image with the vision model instead")
            return mistral.read_image(data, mime)
    raise ProviderError("mistral", "Reading this kind of file needs a Mistral API key (MISTRAL_API_KEY). Notes, Word, PowerPoint and text PDFs work without one.")


def process(m: StudyMaterial, data: bytes, ext: str, content_type: str | None) -> tuple[str | None, str | None]:
    """
    Fill in text and concepts; returns the subject and its broad area if the AI could name them. Failure is recorded on the
    material rather than raised, so the upload itself survives.
    """
    try:
        m.extracted_text = _read(data, ext)[:200000]
        if not m.extracted_text.strip():
            raise ProviderError("mistral", "No readable text was found in this file.")
    except (ProviderError, zipfile.BadZipFile) as e:
        log.error("Material %s could not be read: %s", m.id, getattr(e, "message", "damaged file"))
        m.processing_status, m.processing_error = "FAILED", getattr(e, "message", "This file is damaged and could not be opened.")
        return None, None

    mistral = get_mistral()
    concepts, subject, parent = None, None, None
    if mistral.configured:
        try:
            c = mistral.extract_concepts(m.extracted_text)
            concepts, m.extracted_sections = c.concepts[:12], c.sections[:8]
            subject, parent = c.subject, c.parent_subject
            if c.title:
                m.title = c.title[:200]
        except ProviderError:
            log.warning("Concept extraction unavailable for material %s; using its headings", m.id)
    if concepts is None:
        # no AI: headings stand in for concepts
        heads = re.findall(r"^\s{0,3}#{1,3}\s+(.+)$", m.extracted_text, re.MULTILINE)
        concepts = [h.strip()[:80] for h in heads[:12]]
    m.concepts = concepts
    m.processing_status, m.processing_error = "PROCESSED", None
    return subject, parent


def delete_file(m: StudyMaterial) -> None:
    root = Path(get_settings().upload_dir).resolve()
    path = Path(m.file_path).resolve()
    if root in path.parents and path.exists():
        path.unlink()


def view(m: StudyMaterial, question_count: int = 0) -> dict:
    return {
        "id": m.id, "title": m.title, "file_name": m.file_name, "file_type": m.file_type, "file_size": m.file_size, "topic": m.topic,
        "subject": m.subject or GENERAL, "subject_detected": bool(m.subject), "parent": m.parent_subject or folder_service.place(m.subject)[0],
        "concepts": m.concepts or [], "sections": m.extracted_sections or [], "processing_status": m.processing_status, "processing_error": m.processing_error,
        "has_text": bool(m.extracted_text), "question_count": question_count, "created_at": m.created_at.isoformat() if m.created_at else None,
    }
