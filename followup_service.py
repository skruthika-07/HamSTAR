"""
Follow-up questions for answers that have no diagnostic session (one-word, fill-in-the-blank, brief and
detailed answers). After the correct answer has been explained and the student says "I understood",
Groq writes a fresh multiple-choice question on the same concept: quick to answer, and it can be marked
without another AI call. A wrong follow-up is explained more simply and one more is offered.

Wrong multiple-choice answers do not come through here: their follow-ups are chosen by the diagnostic
engine (app/services/diagnostic_service.py).
"""
from sqlalchemy.orm import Session

from ..core.errors import ApiError
from ..models import Attempt, Question, User
from ..prompts.followup import CONCEPT_FOLLOWUP_PROMPT_VERSION
from . import bank_service
from .explanation_service import _correct_answer
from .groq_service import get_groq

MAX_FOLLOWUPS = 2
LETTERS = "ABCD"


def _log(attempt: Attempt) -> list[dict]:
    # copies, so that saving is seen as a change to the stored JSON
    return [dict(f) for f in (attempt.evaluation or {}).get("followups", [])]


def _save(attempt: Attempt, log: list[dict], **extra) -> None:
    attempt.evaluation = {**(attempt.evaluation or {}), "followups": log, **extra}


def question_ids(attempt: Attempt) -> set[str]:
    """Follow-up questions of this attempt that have been answered (and so may be explained)."""
    return {f["question_id"] for f in _log(attempt) if f.get("selected")}


def next_followup(db: Session, user: User, attempt: Attempt) -> dict:
    """The pending follow-up if there is one, otherwise a newly written one on the same concept."""
    if attempt.is_correct or attempt.skipped:
        raise ApiError("NOTHING_TO_FOLLOW_UP", "Follow-up questions are for answers that were not right.", 409)
    log = _log(attempt)
    pending = next((f for f in log if not f.get("selected")), None)
    if pending:
        return {"attempt_id": attempt.id, "question": bank_service.public(db.get(Question, pending["question_id"])), "number": len(log), "max": MAX_FOLLOWUPS}
    if len(log) >= MAX_FOLLOWUPS:
        raise ApiError("NO_MORE_FOLLOWUPS", "That was the last follow-up for this question.", 409)

    original = db.get(Question, attempt.question_id)
    asked = [original.question_text] + [db.get(Question, f["question_id"]).question_text for f in log]
    # the second one, after a miss, is deliberately easier
    g = get_groq().concept_follow_up(original.question_text, _correct_answer(original)["text"], original.explanation or "", asked, easier=bool(log))
    options = [{"id": LETTERS[i], "text": t.strip(), "correct": LETTERS[i] == g.correct_option, "misconception": None, "reasoning": "", "slip_weight": 1} for i, t in enumerate(g.options)]
    row = Question(
        owner_id=user.id, study_material_id=original.study_material_id, topic=original.topic, role="probe", question_type="MCQ", question_text=g.question.strip(),
        marks=1, options=options, correct_option=g.correct_option, explanation=g.explanation,
        diagnostic_metadata={"parent": original.id, "attempt": attempt.id, "prompt_version": CONCEPT_FOLLOWUP_PROMPT_VERSION},
    )
    db.add(row)
    db.flush()
    log.append({"question_id": row.id, "selected": None, "correct": None})
    _save(attempt, log)
    db.commit()
    return {"attempt_id": attempt.id, "question": bank_service.public(row), "number": len(log), "max": MAX_FOLLOWUPS}


def evaluate_followup(db: Session, user: User, attempt: Attempt, question_id: str, option_id: str) -> dict:
    log = _log(attempt)
    entry = next((f for f in log if f["question_id"] == question_id), None)
    if not entry:
        raise ApiError("INVALID_QUESTION", "That is not a follow-up question for this answer.", 409)
    row = db.get(Question, question_id)
    picked = next((o for o in row.options if o["id"] == option_id), None)
    if not picked:
        raise ApiError("INVALID_OPTION", "That is not one of the options for this question.", 422)
    if not entry.get("selected"):  # answering twice changes nothing
        entry["selected"], entry["correct"] = option_id, bool(picked["correct"])
        # getting a follow-up right is what shows the mistake was learned from; it earns no Tiara
        _save(attempt, log, **({"recovered": True} if picked["correct"] else {}))
        db.commit()
    return {
        "attempt_id": attempt.id,
        "question": bank_service.revealed(row),
        "selected_option": entry["selected"],
        "is_correct": bool(entry["correct"]),
        "recovered": bool((attempt.evaluation or {}).get("recovered")),
        "can_try_another": not entry["correct"] and len(log) < MAX_FOLLOWUPS,
    }
