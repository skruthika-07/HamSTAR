"""
Folders: a broad subject (the parent) holds subtopics (subfolders), and each subfolder holds documents.

    Maths → Fractions → [the starter set, notes.pdf, worksheet.docx]

Every level carries a confidence score and a weakness summary, all worked out here from the student's
answers each time they are asked for, so they are always up to date with the latest attempt.
"""
import re
from collections import Counter, defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..engine import bayes
from ..models import Attempt, MistakeLog, Question, StudyMaterial, User
from . import bank_service

OTHER = "Other"
GENERAL = "General"

# Parent folder → subtopics that belong in it. Suggestions only: any subfolder name is allowed.
TAXONOMY: dict[str, list[str]] = {
    "Maths": ["Algebra", "Fractions", "Calculus", "Statistics", "Probability", "Geometry", "Trigonometry", "Arithmetic", "Number Theory", "Linear Algebra", "Matrices"],
    "Science": ["Physics", "Chemistry", "Biology", "Organic Chemistry", "Environmental Science", "Astronomy", "Botany", "Zoology"],
    "Computer Science": ["Object-Oriented Programming", "OOP", "Data Structures", "Algorithms", "DBMS", "Databases", "Operating Systems", "Computer Networks", "Programming", "Machine Learning", "Web Development", "Software Engineering"],
    "Social Studies": ["History", "Geography", "Civics", "Political Science", "Economics", "Sociology", "Psychology"],
    "Languages": ["English", "Grammar", "Literature", "Hindi", "Tamil", "French", "Spanish"],
    "Commerce": ["Accounting", "Business Studies", "Finance", "Marketing"],
}
# other names a parent folder goes by
PARENT_ALIASES = {
    "maths": "Maths", "math": "Maths", "mathematics": "Maths",
    "science": "Science", "sciences": "Science",
    "computer science": "Computer Science", "cs": "Computer Science", "computing": "Computer Science", "it": "Computer Science", "information technology": "Computer Science",
    "social studies": "Social Studies", "social science": "Social Studies", "humanities": "Social Studies",
    "languages": "Languages", "language": "Languages",
    "commerce": "Commerce", "business": "Commerce",
    "other": OTHER,
}
# when a subtopic is not in the list, its name usually still says where it belongs
PARENT_WORDS = {
    "Maths": r"math|algebra|geometr|calcul|trigono|arithmetic|equation|fraction|statistic|probabilit|matri|vector|number",
    "Science": r"physic|chemi|biolog|scien|mechanic|thermo|optic|electr|magnet|genetic|ecolog|anatom|botan|zoolog|astro|quantum|organic",
    "Computer Science": r"comput|program|software|algorithm|data ?structure|database|dbms|network|operating system|\boop\b|object[- ]oriented|machine learning|\bai\b|web|python|java|\bsql\b|cyber|compiler",
    "Social Studies": r"histor|geograph|civic|politic|econom|sociolog|psycholog|government|culture",
    "Languages": r"english|grammar|literature|poetry|language|hindi|tamil|french|spanish|german|writing|comprehension",
    "Commerce": r"account|business|financ|marketing|commerce|management|banking",
}
# how much one answer counts towards confidence, by question type
TYPE_WEIGHT = {"ONE_WORD": 1.0, "FILL_BLANK": 1.0, "MCQ": 1.0, "SHORT_ANSWER": 2.0, "LONG_ANSWER": 3.0}
# confidence starts from a prior and moves with evidence; this is how much evidence the prior is worth
PRIOR_WEIGHT = 2.0
PRIOR = 0.5


def as_parent(name: str | None) -> str | None:
    """The parent folder a name refers to, if it names one."""
    key = re.sub(r"\s+", " ", (name or "")).strip().lower()
    if not key:
        return None
    if key in PARENT_ALIASES:
        return PARENT_ALIASES[key]
    return next((p for p in TAXONOMY if p.lower() == key), None)


def parent_of(subject: str | None) -> str | None:
    """Which parent folder a subtopic belongs in: by the list first, then by the words in its name."""
    key = (subject or "").strip().lower()
    if not key:
        return None
    for parent, children in TAXONOMY.items():
        if any(c.lower() == key for c in children):
            return parent
    for parent, pattern in PARENT_WORDS.items():
        if re.search(pattern, key):
            return parent
    return None


def clean_parent(name: str | None) -> str | None:
    """A parent folder as typed: a known one by any of its names, or a new one the student is creating."""
    text = re.sub(r"\s+", " ", (name or "")).strip(" .:-\"'")[:80]
    return as_parent(text) or text or None


def place(subject: str | None, parent_hint: str | None = None, ai_parent: str | None = None) -> tuple[str, str | None]:
    """
    (parent, subfolder) for a document. A subject that is itself a broad area ("Mathematics") names the
    parent only: the subfolder is then unknown and the student is asked for it.
    """
    broad = as_parent(subject)
    if broad and broad != OTHER:
        return clean_parent(parent_hint) or broad, None
    parent = clean_parent(parent_hint) or parent_of(subject) or as_parent(ai_parent) or OTHER
    return parent, subject or None


def suggestions() -> list[dict]:
    return [{"name": p, "subfolders": [c for c in children if c != "OOP"]} for p, children in TAXONOMY.items()] + [{"name": OTHER, "subfolders": []}]


# ───────────────────────── scores ─────────────────────────


def _latest(attempts: list[Attempt]) -> dict[str, Attempt]:
    """The most recent real answer to each question (skips are not answers)."""
    out: dict[str, Attempt] = {}
    for a in sorted(attempts, key=lambda a: a.created_at):
        if not a.skipped:
            out[a.question_id] = a
    return out


def _score(questions: list[Question], latest: dict[str, Attempt]) -> dict:
    """Weighted evidence from one set of questions: brief and detailed answers count for more than one-mark ones."""
    weight = earned = 0.0
    answered = correct = 0
    for q in questions:
        a = latest.get(q.id)
        if not a:
            continue
        w = TYPE_WEIGHT.get(q.question_type, 1.0)
        weight += w
        earned += w * max(0.0, min(1.0, (a.percentage or 0) / 100))
        answered += 1
        correct += bool(a.is_correct)
    return {"weight": weight, "earned": earned, "answered": answered, "correct": correct}


def _confidence(earned: float, weight: float, prior: float = PRIOR) -> int:
    return round((earned + PRIOR_WEIGHT * prior) / (weight + PRIOR_WEIGHT) * 100)


def is_weak(answered: int, score: int | None, average: int | None) -> bool:
    """Weak = enough answers to tell, and either a low score or clearly below the student's own average."""
    if answered < 2 or score is None:
        return False
    return score < 60 or (average is not None and score <= average - 15)


def tree(db: Session, user: User) -> dict:
    """Parent folders → subfolders → documents, each with confidence and weakness, weakest first."""
    bank = bank_service.bank(db)
    materials = db.scalars(select(StudyMaterial).where(StudyMaterial.user_id == user.id).order_by(StudyMaterial.created_at)).all()
    starters = {m.topic: m for m in materials if m.file_type == "starter"}
    uploads = [m for m in materials if m.file_type != "starter"]

    own = db.scalars(select(Question).where(Question.owner_id == user.id, Question.role == "main")).all()
    by_material: dict[str, list[Question]] = defaultdict(list)
    for q in own:
        by_material[q.study_material_id].append(q)
    shared = db.scalars(select(Question).where(Question.owner_id.is_(None), Question.role == "main")).all()
    latest = _latest(db.scalars(select(Attempt).where(Attempt.user_id == user.id)).all())

    logs = db.scalars(select(MistakeLog).where(MistakeLog.user_id == user.id, MistakeLog.resolved.is_(False))).all()
    wrong_by_doc: dict[str, Counter] = defaultdict(Counter)
    names: dict[str, str] = {}
    for log in logs:
        wrong_by_doc[log.document][log.concept_key] += 1
        names[log.concept_key] = log.concept

    documents: list[dict] = []
    cursors = user.cursors or {}

    def add(doc: dict, s: dict, prior: float) -> None:
        doc.update({
            "answered": s["answered"], "correct": s["correct"],
            "score": round(s["earned"] / s["weight"] * 100) if s["weight"] else None,
            "confidence": _confidence(s["earned"], s["weight"], prior),
            "weak_concepts": [{"concept": names[k], "count": n} for k, n in wrong_by_doc[doc["id"]].most_common(3)],
            "_w": s["weight"], "_e": s["earned"], "_p": prior,
        })
        documents.append(doc)

    hidden = 0
    for t in bank.topics:
        mains = [q for q in shared if q.topic == t["id"]]
        starter = starters.get(t["id"])
        if starter and starter.processing_status == "HIDDEN":  # the student deleted this starter set
            hidden += 1
            continue
        extra = by_material.get(starter.id, []) if starter else []
        belief = (user.beliefs or {}).get(t["id"], bank.prior(t["id"]))
        # the verified set already has a confidence from the diagnosis engine: it is the starting point here,
        # and every answer in the folder then moves it, so a wrong answer shows at once (before any diagnosis)
        s = _score(mains + extra, latest)
        doc = {
            "id": t["id"], "kind": "starter", "material_id": None, "title": f"{t['name']} starter set", "file_name": t["blurb"], "file_type": "starter",
            "subject": starter_place(starter, t["name"])[1], "parent": starter_place(starter, t["name"])[0], "subject_detected": True, "processing_status": "PROCESSED", "processing_error": None,
            "question_count": len(mains) + len(extra), "question_number": min(cursors.get(t["id"], 0) + 1, max(len(mains), 1)), "completed": bool(mains) and cursors.get(t["id"], 0) >= len(mains),
        }
        add(doc, s, bayes.understanding(belief) if belief else PRIOR)

    for m in uploads:
        qs = by_material.get(m.id, [])
        mcq = [q for q in qs if q.question_type == "MCQ"]
        position = cursors.get(f"material:{m.id}", 0)
        parent, _ = place(m.subject, m.parent_subject)
        doc = {
            "id": f"material:{m.id}", "kind": "upload", "material_id": m.id, "title": m.title, "file_name": m.file_name, "file_type": m.file_type,
            "subject": m.subject or GENERAL, "parent": m.parent_subject or parent, "subject_detected": bool(m.subject), "processing_status": m.processing_status, "processing_error": m.processing_error,
            "question_count": len(qs), "question_number": min(position + 1, max(len(mcq), 1)), "completed": bool(mcq) and position >= len(mcq),
        }
        add(doc, _score(qs, latest), PRIOR)

    scored = [d for d in documents if d["score"] is not None]
    answered = sum(d["answered"] for d in scored)
    average = round(sum(d["score"] * d["answered"] for d in scored) / answered) if answered else None
    for d in documents:
        d["weak"] = is_weak(d["answered"], d["score"], average)
        d["vs_average"] = d["score"] - average if d["score"] is not None and average is not None else None

    def combined(docs: list[dict]) -> int:
        # documents with more evidence behind them count for more
        w = sum(d["_w"] + PRIOR_WEIGHT for d in docs)
        return round(sum(d["_e"] + PRIOR_WEIGHT * d["_p"] for d in docs) / w * 100) if w else round(PRIOR * 100)

    def weakest_first(d: dict):
        # weak ones first, then those in progress by confidence, then untouched ones
        return (0 if d["weak"] else 1 if d["answered"] else 2, d["confidence"], d["title"].lower())

    grouped: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for d in documents:
        grouped[d["parent"]][d["subject"]].append(d)

    folders = []
    for parent, subs in grouped.items():
        subfolders = []
        for name, docs in subs.items():
            docs.sort(key=weakest_first)
            subfolders.append({
                "name": name, "confidence": combined(docs), "answered": sum(d["answered"] for d in docs), "document_count": len(docs),
                "weak": any(d["weak"] for d in docs), "documents": docs,
            })
        subfolders.sort(key=lambda s: (0 if s["weak"] else 1 if s["answered"] else 2, s["confidence"], s["name"].lower()))
        every = [d for s in subfolders for d in s["documents"]]
        tried = [s for s in subfolders if s["answered"]]
        weakest = min(tried, key=lambda s: s["confidence"]) if tried else None
        folders.append({
            "name": parent, "confidence": combined(every), "answered": sum(d["answered"] for d in every), "document_count": len(every),
            # named only when there is something to improve: a weak subfolder, or one clearly behind the others
            "weakest": {"subfolder": weakest["name"], "confidence": weakest["confidence"], "document": weakest["documents"][0]["id"]}
            if weakest and (weakest["weak"] or (len(tried) > 1 and weakest["confidence"] < 70)) else None,
            "subfolders": subfolders,
        })
    folders.sort(key=lambda f: (f["name"] == OTHER, f["name"].lower()))
    total = combined(documents) if documents else 0
    for d in documents:
        for k in ("_w", "_e", "_p"):
            d.pop(k)
    return {"folders": folders, "total_confidence": total, "average_score": average, "suggestions": suggestions(), "hidden_starters": hidden}


# ───────────────────────── renaming ─────────────────────────


def starter_place(starter: StudyMaterial | None, name: str) -> tuple[str, str]:
    """(parent, subfolder) of a starter set: where it has been renamed to, or where it starts out."""
    return (starter.parent_subject if starter and starter.parent_subject else parent_of(name) or OTHER, starter.subject if starter and starter.subject else name)


def rename(db: Session, user: User, parent: str, subfolder: str | None, name: str) -> int:
    """
    Rename a parent folder, or one subfolder inside it. Everything filed there moves with the name: uploads,
    the starter set, the questions written from them and the mistake log. Returns how many documents moved.
    Renaming onto a folder that already exists merges the two.
    """
    from ..core.errors import ApiError  # local: keeps this module free of web concerns at import time

    new = re.sub(r"\s+", " ", name or "").strip(" .:-\"'")[:80]
    if not new:
        raise ApiError("INVALID_FOLDER_NAME", "A folder needs a name.", 422)
    same = lambda a, b: (a or "").strip().lower() == (b or "").strip().lower()  # noqa: E731

    materials = list(db.scalars(select(StudyMaterial).where(StudyMaterial.user_id == user.id)).all())
    starters = {m.topic: m for m in materials if m.file_type == "starter"}
    targets: list[tuple[StudyMaterial, str, str]] = []
    for t in bank_service.bank(db).topics:
        p, s = starter_place(starters.get(t["id"]), t["name"])
        if same(p, parent) and (subfolder is None or same(s, subfolder)):
            # a starter set is shared content: its own name for this student lives on their hidden starter material
            targets.append((bank_service.starter_material(db, user, t["id"]), p, s))
    for m in materials:
        if m.file_type == "starter":
            continue
        p, s = m.parent_subject or place(m.subject)[0], m.subject or GENERAL
        if same(p, parent) and (subfolder is None or same(s, subfolder)):
            targets.append((m, p, s))
    if not targets:
        raise ApiError("FOLDER_NOT_FOUND", "That folder was not found.", 404)

    for m, p, s in targets:
        if subfolder is None:
            m.parent_subject = new
            if m.file_type == "starter" and not m.subject:
                m.subject = s
        else:
            m.parent_subject, m.subject = p, new  # the parent is pinned, so the new name cannot move it elsewhere
            for q in m.questions:
                q.topic = new
    for log in db.scalars(select(MistakeLog).where(MistakeLog.user_id == user.id)):
        if same(log.parent, parent) and (subfolder is None or same(log.folder, subfolder)):
            if subfolder is None:
                log.parent = new
            else:
                log.folder = new
    db.commit()
    return len(targets)


# ───────────────────────── deleting ─────────────────────────

HIDDEN = "HIDDEN"


def _wipe_attempts(db: Session, user: User, question_ids: list[str]) -> None:
    """The student's answers to these questions, with their diagnoses and mistake log."""
    if not question_ids:
        return
    for log in db.scalars(select(MistakeLog).where(MistakeLog.user_id == user.id, MistakeLog.question_id.in_(question_ids))):
        db.delete(log)
    attempts = list(db.scalars(select(Attempt).where(Attempt.user_id == user.id, Attempt.question_id.in_(question_ids))))
    from . import answer_image_service

    answer_image_service.delete_files(db, [a.id for a in attempts])
    for a in attempts:
        db.delete(a)  # cascades to diagnostic sessions and their follow-ups
    db.flush()


def _forget(user: User, *prefixes: str) -> None:
    user.cursors = {k: v for k, v in (user.cursors or {}).items() if not any(k == p or k.startswith(p + "|") for p in prefixes)}


def delete(db: Session, user: User, parent: str, subfolder: str | None) -> int:
    """
    Delete a parent folder (with every subfolder in it) or one subfolder: the documents, their files, the
    questions written from them and the student's progress on them all go. A starter set is shared content, so
    for it the student's progress is erased and the set is hidden from their folders (it can be brought back).
    Returns how many documents were removed.
    """
    from ..core.errors import ApiError
    from . import document_service

    same = lambda a, b: (a or "").strip().lower() == (b or "").strip().lower()  # noqa: E731
    hit = lambda p, s: same(p, parent) and (subfolder is None or same(s, subfolder))  # noqa: E731
    materials = list(db.scalars(select(StudyMaterial).where(StudyMaterial.user_id == user.id)).all())
    starters = {m.topic: m for m in materials if m.file_type == "starter"}
    removed = 0

    for t in bank_service.bank(db).topics:
        starter = starters.get(t["id"])
        if (starter and starter.processing_status == HIDDEN) or not hit(*starter_place(starter, t["name"])):
            continue
        starter = bank_service.starter_material(db, user, t["id"])
        shared = list(db.scalars(select(Question.id).where(Question.owner_id.is_(None), Question.topic == t["id"])))
        own = list(starter.questions)
        _wipe_attempts(db, user, shared + [q.id for q in own])
        for q in own:
            db.delete(q)
        user.beliefs = {k: v for k, v in (user.beliefs or {}).items() if k != t["id"]}
        _forget(user, t["id"], f"material:{starter.id}")
        for log in db.scalars(select(MistakeLog).where(MistakeLog.user_id == user.id, MistakeLog.document == t["id"])):
            db.delete(log)
        starter.processing_status = HIDDEN
        removed += 1

    for m in materials:
        if m.file_type == "starter" or not hit(m.parent_subject or place(m.subject)[0], m.subject or GENERAL):
            continue
        _wipe_attempts(db, user, [q.id for q in m.questions])
        _forget(user, f"material:{m.id}")
        document_service.delete_file(m)
        db.delete(m)  # its questions go with it
        removed += 1

    if not removed:
        raise ApiError("FOLDER_NOT_FOUND", "That folder was not found.", 404)
    db.commit()
    return removed


def restore_starters(db: Session, user: User) -> int:
    """Bring back starter sets that were deleted from this student's folders (as new: the old progress is gone)."""
    rows = db.scalars(select(StudyMaterial).where(StudyMaterial.user_id == user.id, StudyMaterial.file_type == "starter", StudyMaterial.processing_status == HIDDEN)).all()
    for m in rows:
        m.processing_status = "PROCESSED"
    db.commit()
    return len(rows)
