"""
Every wrong answer is logged with its concept, the kind of mistake and where it came from. A concept that
goes wrong twice or more, and has not been put right since, is a recurring mistake: the student is told,
and offered a short drill on exactly that concept. Two correct answers on the concept put it right.
"""
from collections import Counter, defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import ApiError
from ..models import Attempt, Misconception, MistakeLog, Question, StudyMaterial, User
from . import bank_service, folder_service

RECURRING_AT = 2
FIXES_TO_RESOLVE = 2
DRILL_SIZE = 5
PRACTICE_SIZE = 8


def key_of(concept: str) -> str:
    return " ".join(concept.lower().split())[:120]


def document_of(db: Session, q: Question, user: User | None = None) -> tuple[str, str, str]:
    """(document id, subfolder, parent folder) a question belongs to. With `user`, in the names that student gave them."""
    starter = None
    if q.study_material_id:
        m = db.get(StudyMaterial, q.study_material_id)
        if m and m.file_type != "starter":
            parent, _ = folder_service.place(m.subject, m.parent_subject)
            return f"material:{m.id}", m.subject or folder_service.GENERAL, m.parent_subject or parent
        topic, starter = (m.topic, m) if m else (q.topic, None)
    else:
        topic = q.topic
    name = next((t["name"] for t in bank_service.bank(db).topics if t["id"] == topic), topic)
    if starter is None and user is not None:
        starter = db.scalar(select(StudyMaterial).where(StudyMaterial.user_id == user.id, StudyMaterial.file_type == "starter", StudyMaterial.topic == topic))
    parent, folder = folder_service.starter_place(starter, name)
    return topic, folder, parent


def _misconception_names(db: Session, ids: list[str | None]) -> list[str]:
    out = []
    for i in ids:
        m = db.get(Misconception, i) if i and not i.startswith("GEN:") else None
        if m and m.name not in out:
            out.append(m.name)
    return out


def concepts_of(db: Session, q: Question) -> list[str]:
    """Every concept a question is about. A correct answer counts towards putting any of them right."""
    meta = q.diagnostic_metadata or {}
    names = _misconception_names(db, [meta.get("targets"), *[o.get("misconception") for o in q.options or []]])
    if meta.get("concept"):
        names.append(str(meta["concept"]).strip()[:120])
    if not names and meta.get("parent"):  # a follow-up question is about what its original was about
        parent = db.get(Question, meta["parent"])
        if parent:
            return concepts_of(db, parent)
    return names or [document_of(db, q)[1]]


def concept_of(db: Session, q: Question, attempt: Attempt) -> str:
    """The one concept a wrong answer points at: for multiple choice, the idea behind the option chosen."""
    picked = next((o for o in q.options or [] if o["id"] == attempt.selected_option), {})
    names = _misconception_names(db, [picked.get("misconception")])
    return (names or concepts_of(db, q))[0]


def record_wrong(db: Session, user: User, q: Question, attempt: Attempt) -> dict | None:
    """Log the mistake. Returns a warning when this concept has now gone wrong twice or more."""
    from .explanation_service import _guess_mistake_type  # a first impression; refined when the answer is explained

    concept = concept_of(db, q, attempt)
    document, folder, parent = document_of(db, q, user)
    db.add(MistakeLog(user_id=user.id, attempt_id=attempt.id, question_id=q.id, concept=concept, concept_key=key_of(concept), document=document, folder=folder, parent=parent, mistake_type=_guess_mistake_type(attempt, q)))
    db.flush()
    count = len(db.scalars(select(MistakeLog.id).where(MistakeLog.user_id == user.id, MistakeLog.concept_key == key_of(concept), MistakeLog.resolved.is_(False))).all())
    if count < RECURRING_AT:
        return None
    return {"concept": concept, "count": count, "folder": folder, "message": f"You keep making this mistake in {concept} — let's fix this!"}


def record_right(db: Session, user: User, q: Question) -> None:
    """A correct answer on a concept with open mistakes counts towards putting it right."""
    keys = {key_of(c) for c in concepts_of(db, q)}
    rows = db.scalars(select(MistakeLog).where(MistakeLog.user_id == user.id, MistakeLog.concept_key.in_(keys), MistakeLog.resolved.is_(False))).all()
    groups: dict[str, list[MistakeLog]] = defaultdict(list)
    for r in rows:
        groups[r.concept_key].append(r)
    for group in groups.values():
        fixes = max(r.fixes for r in group) + 1
        for r in group:
            r.fixes = fixes
            r.resolved = fixes >= FIXES_TO_RESOLVE


def set_type(db: Session, attempt: Attempt, kind: str) -> None:
    """Once the kind of mistake has been worked out properly, the log is brought into line with it."""
    row = db.scalar(select(MistakeLog).where(MistakeLog.attempt_id == attempt.id))
    if row:
        row.mistake_type = kind


def summary(db: Session, user: User) -> dict:
    """Recurring concepts (most repeated first) and the kinds of mistake that keep coming back."""
    from .explanation_service import MISTAKE_LABELS

    rows = db.scalars(select(MistakeLog).where(MistakeLog.user_id == user.id, MistakeLog.resolved.is_(False)).order_by(MistakeLog.created_at)).all()
    groups: dict[str, list[MistakeLog]] = defaultdict(list)
    for r in rows:
        groups[r.concept_key].append(r)
    recurring = []
    for group in groups.values():
        if len(group) < RECURRING_AT:
            continue
        last = group[-1]
        kinds = Counter(r.mistake_type for r in group)
        kind = kinds.most_common(1)[0][0]
        recurring.append({
            "concept": last.concept, "count": len(group), "folder": last.folder, "parent": last.parent, "documents": sorted({r.document for r in group}),
            "mistake_type": {"kind": kind, "label": MISTAKE_LABELS[kind][0]}, "mistake_types": dict(kinds),
            "fixes": max(r.fixes for r in group), "fixes_needed": FIXES_TO_RESOLVE,
            "last_at": last.created_at.isoformat(), "message": f"You keep making this mistake in {last.concept} — let's fix this!",
        })
    recurring.sort(key=lambda r: (-r["count"], r["last_at"]), reverse=False)
    kinds = Counter(r.mistake_type for r in rows)
    patterns = [{"kind": k, "label": MISTAKE_LABELS[k][0], "about": MISTAKE_LABELS[k][1], "count": n} for k, n in kinds.most_common() if n >= RECURRING_AT and k in MISTAKE_LABELS]
    return {"recurring": recurring, "patterns": patterns, "logged": len(rows)}


# ───────────────────────── focused practice ─────────────────────────


def _visible(db: Session, user: User) -> list[Question]:
    return list(db.scalars(select(Question).where((Question.owner_id == user.id) | (Question.owner_id.is_(None)))).all())


def drill(db: Session, user: User, concept: str) -> dict:
    """A mini-drill on one concept: the questions that went wrong, then others on the same idea."""
    key = key_of(concept)
    logs = db.scalars(select(MistakeLog).where(MistakeLog.user_id == user.id, MistakeLog.concept_key == key).order_by(MistakeLog.created_at.desc())).all()
    if not logs:
        raise ApiError("NOTHING_TO_DRILL", "There are no mistakes logged for that concept.", 404)
    missed, picked = [], []
    for log in logs:
        if log.question_id not in missed:
            missed.append(log.question_id)
    documents = {log.document for log in logs}
    # follow-up questions written for one answer are not reused; the verified bank's own probes are
    others = [q for q in _visible(db, user) if q.id not in missed and (q.role == "main" or q.owner_id is None) and key in {key_of(c) for c in concepts_of(db, q)} and document_of(db, q)[0] in documents]
    others.sort(key=lambda q: (q.role != "probe", q.created_at))  # fresh questions on the idea come before repeats
    for q in [*others[: DRILL_SIZE - min(len(missed), 2)], *[db.get(Question, i) for i in missed]]:
        if q and len(picked) < DRILL_SIZE:
            picked.append(q)
    return {"kind": "concept", "title": logs[0].concept, "folder": logs[0].folder, "questions": [bank_service.public(q) for q in picked]}


def practice(db: Session, user: User, document: str) -> dict:
    """A focused session on one document: what went wrong first, then what has not been tried."""
    if document.startswith("material:"):
        m = db.get(StudyMaterial, document.split(":", 1)[1])
        if not m or m.user_id != user.id:
            raise ApiError("STUDY_MATERIAL_NOT_FOUND", "That document was not found.", 404)
        questions = db.scalars(select(Question).where(Question.study_material_id == m.id, Question.owner_id == user.id, Question.role == "main").order_by(Question.created_at, Question.id)).all()
        title, folder = m.title, m.subject or folder_service.GENERAL
    elif bank_service.is_bank_topic(document):
        starter = db.scalar(select(StudyMaterial).where(StudyMaterial.user_id == user.id, StudyMaterial.file_type == "starter", StudyMaterial.topic == document))
        questions = sorted(db.scalars(select(Question).where(Question.owner_id.is_(None), Question.topic == document, Question.role == "main")).all(), key=lambda q: (q.diagnostic_metadata or {}).get("position", 0))
        if starter:
            questions += db.scalars(select(Question).where(Question.study_material_id == starter.id, Question.role == "main").order_by(Question.created_at)).all()
        folder = next(t["name"] for t in bank_service.bank(db).topics if t["id"] == document)
        title = f"{folder} starter set"
    else:
        raise ApiError("STUDY_MATERIAL_NOT_FOUND", "That document was not found.", 404)
    if not questions:
        raise ApiError("NO_QUESTIONS_OF_TYPE", "This document has no questions yet. Write some first.", 404)

    latest: dict[str, Attempt] = {}
    ids = [q.id for q in questions]
    for a in db.scalars(select(Attempt).where(Attempt.user_id == user.id, Attempt.question_id.in_(ids), Attempt.skipped.is_(False)).order_by(Attempt.created_at)):
        latest[a.question_id] = a
    wrong = [q for q in questions if q.id in latest and not latest[q.id].is_correct]
    untried = [q for q in questions if q.id not in latest]
    right = [q for q in questions if q.id in latest and latest[q.id].is_correct]
    picked = [*wrong, *untried, *right][:PRACTICE_SIZE]
    return {"kind": "document", "title": title, "folder": folder, "questions": [bank_service.public(q) for q in picked]}
