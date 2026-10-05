"""Routes an answer to the right evaluation for its question type, and applies the outcome exactly once."""
import difflib
import re
from contextvars import ContextVar
from fractions import Fraction

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.errors import ApiError
from ..engine import bayes
from ..engine.bank import option
from ..models import Attempt, DiagnosticSession, Question, User
from ..prompts.answer_evaluation import ANSWER_EVALUATION_PROMPT_VERSION
from . import bank_service, diagnostic_service, mistake_service, reward_service
from .ai_client import ProviderError
from .groq_service import get_groq


# set while a practice or drill answer is evaluated: it counts, but the folder's position stays where it is
_practice: ContextVar[bool] = ContextVar("practice", default=False)


def folder_key(base: str, question_type: str) -> str:
    """Where a student is in a folder is tracked separately for each question type."""
    return base if question_type == "MCQ" else f"{base}|{question_type}"


def cursor_key(question: Question) -> str:
    return folder_key(f"material:{question.study_material_id}" if question.study_material_id else question.topic, question.question_type)


def _advance(user: User, question: Question, total: int) -> None:
    key = cursor_key(question)
    cursors = dict(user.cursors or {})
    # the position only moves forward; reaching the end means the set is complete (it does not wrap round)
    cursors[key] = min(cursors.get(key, 0) + 1, max(total, 1))
    user.cursors = cursors


def completion(db: Session, user: User, key: str) -> dict:
    """How the student did on one folder's set of questions, counted on their latest answer to each."""
    questions = question_list(db, user, key)
    ids = [q.id for q in questions]
    latest: dict[str, Attempt] = {}
    if ids:
        for a in db.scalars(select(Attempt).where(Attempt.user_id == user.id, Attempt.question_id.in_(ids)).order_by(Attempt.created_at)):
            latest[a.question_id] = a
    answered = [a for a in latest.values() if not a.skipped]
    correct = sum(a.is_correct for a in answered)
    position = (user.cursors or {}).get(key, 0)
    return {
        "total": len(questions),
        "attempted": len(answered),
        "correct": correct,
        "wrong": len(answered) - correct,
        "skipped": sum(a.skipped for a in latest.values()),
        "score": round(correct / len(answered) * 100) if answered else 0,
        "completed": bool(questions) and position >= len(questions),
    }


def restart(db: Session, user: User, key: str) -> None:
    """Go through a finished set again from its first question."""
    user.cursors = {**(user.cursors or {}), key: 0}
    db.commit()


def question_list(db: Session, user: User, key: str) -> list[Question]:
    """The learning questions behind a cursor: a bank topic, or the set generated from one uploaded material."""
    key, _, question_type = key.partition("|")
    question_type = question_type or "MCQ"
    if key.startswith("material:"):
        rows = db.scalars(select(Question).where(Question.study_material_id == key.split(":", 1)[1], Question.owner_id == user.id, Question.role == "main", Question.question_type == question_type).order_by(Question.created_at, Question.id)).all()
        return list(rows)
    if question_type != "MCQ":
        return []  # the verified bank is multiple choice; other types for a bank folder live in its starter material
    rows = db.scalars(select(Question).where(Question.owner_id.is_(None), Question.topic == key, Question.role == "main")).all()
    return sorted(rows, key=lambda q: (q.diagnostic_metadata or {}).get("position", 0))


def _normal(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[.,;:!?\"']+$", "", (text or "").strip().lower())).strip()


def _number(text: str) -> Fraction | None:
    t = _normal(text).replace(" ", "")
    try:
        return Fraction(t[:-1]) / 100 if t.endswith("%") else Fraction(t)
    except (ValueError, ZeroDivisionError):
        return None


def _stored_result(db: Session, attempt: Attempt) -> dict:
    """The response for an attempt that already exists: nothing is awarded a second time."""
    user = db.get(User, attempt.user_id)
    out = dict(attempt.evaluation or {})
    out.update({"attempt_id": attempt.id, "tiara_awarded": 0, "new_tiara_count": user.tiara_count, "streak_updated": False, "duplicate": True, "unlocked": []})
    session = db.scalar(select(DiagnosticSession).where(DiagnosticSession.attempt_id == attempt.id))
    if session:
        out["diagnostic"] = diagnostic_service.view(db, session)
    return out


def evaluate(db: Session, user: User, question: Question, answer: str | None, selected_option: str | None, reasoning: str | None, client_key: str | None, practice: bool = False) -> dict:
    if client_key:
        existing = db.scalar(select(Attempt).where(Attempt.user_id == user.id, Attempt.client_key == client_key))
        if existing:
            return _stored_result(db, existing)

    kind = question.question_type
    token = _practice.set(practice)
    try:
        if kind == "MCQ":
            result = _mcq(db, user, question, selected_option or (answer or "").strip().upper()[:1], reasoning, client_key)
        elif kind in ("FILL_BLANK", "ONE_WORD"):
            result = _fill_blank(db, user, question, answer or "", reasoning, client_key)
        else:
            result = _written(db, user, question, answer or "", reasoning, client_key)
        db.commit()
    except IntegrityError:
        # the same submission arrived twice at once: the first one won
        db.rollback()
        existing = db.scalar(select(Attempt).where(Attempt.user_id == user.id, Attempt.client_key == client_key))
        if existing:
            return _stored_result(db, existing)
        raise
    finally:
        _practice.reset(token)
    return result


def _finish(db: Session, user: User, question: Question, attempt: Attempt, correct: bool, body: dict) -> dict:
    """Shared ending: counters, Tiara, cursor, unlocks. `body` is what gets stored and returned."""
    reward_service.record_answer(user, correct)
    tiara = reward_service.award_tiara(db, user, attempt.id) if correct else 0
    if not _practice.get():
        _advance(user, question, len(question_list(db, user, cursor_key(question))))
    unlocked = reward_service.check_unlocks(db, user)
    body = {
        "is_correct": correct, "marks_awarded": attempt.marks_awarded, "total_marks": attempt.total_marks, "percentage": attempt.percentage,
        "question_type": question.question_type, **body,
    }
    attempt.evaluation = body
    # every wrong answer is logged; a concept that keeps going wrong is flagged, and a right answer helps clear it
    if correct:
        mistake_service.record_right(db, user, question)
    else:
        body["recurring"] = mistake_service.record_wrong(db, user, question, attempt)
        attempt.evaluation = dict(body)
    return {**body, "attempt_id": attempt.id, "tiara_awarded": tiara, "new_tiara_count": user.tiara_count, "streak_updated": correct, "current_streak": user.current_streak, "duplicate": False, "unlocked": unlocked}


def _mcq(db: Session, user: User, question: Question, selected: str, reasoning: str | None, client_key: str | None) -> dict:
    qd = bank_service.q_dict(question)
    picked = option(qd, selected)
    if not picked:
        raise ApiError("INVALID_OPTION", "Choose one of the options for this question.", 422)
    correct = bool(picked["correct"])

    prior, _, _ = bank_service.context(db, question)
    in_bank = question.owner_id is None and bank_service.is_bank_topic(question.topic)
    # earlier evidence still counts, but fades, so an old label can be overturned by what the student does now
    belief_before = bayes.carry_over((user.beliefs or {}).get(question.topic, prior), prior) if in_bank else prior

    attempt = Attempt(user_id=user.id, question_id=question.id, client_key=client_key, answer=picked["text"], selected_option=selected, reasoning=(reasoning or None),
                      marks_awarded=1.0 if correct else 0.0, total_marks=1.0, percentage=100.0 if correct else 0.0, is_correct=correct)
    db.add(attempt)
    db.flush()

    if correct:
        after = bayes.update(belief_before, qd, selected)
        if in_bank:
            user.beliefs = {**(user.beliefs or {}), question.topic: after}
        attempt.confidence = round(bayes.understanding(after) * 100, 1)
        # a correct MCQ needs no diagnostic session and no AI call
        result = _finish(db, user, question, attempt, True, {"question": bank_service.revealed(question), "feedback": question.explanation, "confidence": attempt.confidence})
        result["diagnostic"] = None
        return result

    # wrong: the specific option is kept as evidence; nothing is labelled yet and the answer is not revealed
    result = _finish(db, user, question, attempt, False, {"question": bank_service.public(question), "feedback": "Let's figure out why this answer happened.", "confidence": None})
    session = diagnostic_service.start(db, user, attempt, question, belief_before)
    result["diagnostic"] = diagnostic_service.view(db, session)
    return result


def _fill_blank(db: Session, user: User, question: Question, answer: str, reasoning: str | None, client_key: str | None) -> dict:
    if not answer.strip():
        raise ApiError("EMPTY_ANSWER", "Write an answer first, or skip the question.", 422)
    accepted = [question.expected_answer or "", *(question.accepted_answers or [])]
    norm = _normal(answer)
    given_n = _number(answer)
    # spacing never matters: "5x - 4" is "5x-4"
    tight = lambda s: re.sub(r"\s+", "", _normal(s))  # noqa: E731
    exact = norm in {_normal(a) for a in accepted} or tight(answer) in {tight(a) for a in accepted if a} or (given_n is not None and any(_number(a) == given_n for a in accepted))

    feedback, confidence = question.explanation, 95.0
    if exact:
        classification = "CORRECT"
    else:
        classification, confidence = None, 40.0
        groq = get_groq()
        if groq.configured:
            try:
                j = groq.judge_fill_blank(question.question_text, question.expected_answer or "", question.accepted_answers or [], answer)
                classification, feedback, confidence = j.classification, j.feedback or feedback, j.confidence
            except ProviderError:
                classification = None
        if classification is None:
            # no AI available: only judgements that can be made safely without one
            close = max((difflib.SequenceMatcher(None, norm, _normal(a)).ratio() for a in accepted), default=0)
            classification = "MINOR_ERROR" if close >= 0.85 else "CALCULATION_ERROR" if given_n is not None and _number(question.expected_answer or "") is not None else "UNCLASSIFIED"

    correct = classification in ("CORRECT", "MINOR_ERROR")
    marks = float(question.marks) if classification == "CORRECT" else question.marks / 2 if classification == "MINOR_ERROR" else 0.0
    attempt = Attempt(user_id=user.id, question_id=question.id, client_key=client_key, answer=answer[:2000], reasoning=reasoning or None, marks_awarded=marks,
                      total_marks=float(question.marks), percentage=round(marks / question.marks * 100, 1), is_correct=correct, confidence=confidence)
    db.add(attempt)
    db.flush()
    result = _finish(db, user, question, attempt, correct, {"classification": classification, "question": bank_service.revealed(question), "feedback": feedback, "confidence": confidence, "expected_answer": question.expected_answer})
    result["diagnostic"] = None
    return result


def _written(db: Session, user: User, question: Question, answer: str, reasoning: str | None, client_key: str | None) -> dict:
    """
    Short and long answers are marked by Groq on the concepts they cover, against the rubric Mistral wrote
    with the question. Wording is never compared: there is no string matching for these types.
    """
    if not answer.strip():
        raise ApiError("EMPTY_ANSWER", "Write an answer first, or skip the question.", 422)
    meta = question.diagnostic_metadata or {}
    grade = get_groq().grade_written(question.question_type, question.question_text, question.marks, question.model_answer or "", question.rubric or [], meta.get("expected_concepts", []), answer)
    pct = round(grade.marks_awarded / question.marks * 100, 1)
    # the bar is the understanding threshold, never 50%
    correct = pct > get_settings().understanding_threshold
    attempt = Attempt(user_id=user.id, question_id=question.id, client_key=client_key, answer=answer[:20000], reasoning=reasoning or None, marks_awarded=grade.marks_awarded,
                      total_marks=float(question.marks), percentage=pct, is_correct=correct, confidence=grade.confidence)
    db.add(attempt)
    db.flush()
    result = _finish(db, user, question, attempt, correct, {
        # structured feedback: what was right, what a full answer includes, and only what was genuinely missed
        "keywords_matched": grade.keywords_matched, "concepts_covered": grade.concepts_covered, "complete_answer": grade.complete_answer or (question.model_answer or ""),
        "missing_concepts": grade.missing_concepts, "misconceptions": grade.misconceptions, "feedback": grade.feedback, "evidence": grade.evidence,
        "confidence": grade.confidence, "question": bank_service.revealed(question), "prompt_version": ANSWER_EVALUATION_PROMPT_VERSION,
    })
    result["diagnostic"] = None
    return result


def skip(db: Session, user: User, question: Question, client_key: str | None, practice: bool = False) -> dict:
    """No Tiara, no mistake, no diagnosis. Only the streaks are affected."""
    if client_key and (existing := db.scalar(select(Attempt).where(Attempt.user_id == user.id, Attempt.client_key == client_key))):
        return {"attempt_id": existing.id, "skipped": True, "duplicate": True, "current_streak": user.current_streak}
    attempt = Attempt(user_id=user.id, question_id=question.id, client_key=client_key, skipped=True, total_marks=float(question.marks), evaluation={"skipped": True})
    db.add(attempt)
    reward_service.record_skip(user)
    if not practice:
        _advance(user, question, len(question_list(db, user, cursor_key(question))))
    db.commit()
    return {"attempt_id": attempt.id, "skipped": True, "duplicate": False, "current_streak": user.current_streak}
