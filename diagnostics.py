from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.errors import ApiError, not_found, ok
from ..core.security import current_user
from ..engine import bayes
from ..models import Attempt, DiagnosticSession, Question, User
from ..schemas.requests import DiagnosticCreate, Envelope, ExplainRequest, FollowUpAnswer, ReasoningRequest
from ..services import bank_service, diagnostic_service, explanation_service
from .deps import AUTH_ERRORS, own_session

router = APIRouter(prefix="/api/diagnostics", tags=["Diagnostics"], responses={**AUTH_ERRORS, 404: {"description": "DIAGNOSTIC_NOT_FOUND"}, 403: {"description": "FORBIDDEN"}})


@router.post("", response_model=Envelope, summary="Open (or fetch) the diagnostic session for a wrong attempt", responses={404: {"description": "ATTEMPT_NOT_FOUND"}})
def create(body: DiagnosticCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """`/api/attempts/evaluate` opens the session itself for a wrong MCQ; this is for fetching it by attempt, and it never creates a second one."""
    attempt = db.get(Attempt, body.attempt_id)
    if not attempt or attempt.user_id != user.id:
        raise not_found("attempt")
    s = db.scalar(select(DiagnosticSession).where(DiagnosticSession.attempt_id == attempt.id))
    if not s:
        question = db.get(Question, attempt.question_id)
        if attempt.is_correct or attempt.skipped or question.question_type != "MCQ":
            raise ApiError("NOTHING_TO_DIAGNOSE", "Only a wrong multiple-choice answer opens a diagnosis.", 409)
        prior, _, _ = bank_service.context(db, question)
        s = diagnostic_service.start(db, user, attempt, question, bayes.carry_over((user.beliefs or {}).get(question.topic, prior), prior))
        db.commit()
    return ok(diagnostic_service.view(db, s))


@router.get("/{session_id}", response_model=Envelope, summary="The current state of a diagnosis")
def get(session_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return ok(diagnostic_service.view(db, own_session(db, user, session_id)))


@router.post("/{session_id}/explain", response_model=Envelope, summary="Show the correct answer and explain it", responses={422: {"description": "INVALID_QUESTION"}})
def explain(session_id: str, body: ExplainRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """
    The first thing a student sees after a wrong answer: the correct answer and a clear explanation of it,
    with nothing said about why their own answer was wrong. `level` 1 and up re-explain the same idea more
    simply with an everyday example. `question_id` may name one of this session's follow-up or retest
    questions that has already been answered; by default the original question is explained.
    """
    s = own_session(db, user, session_id)
    answered = {s.question_id, *(st["question_id"] for st in s.steps or []), *(r["question_id"] for r in s.retry or [])}
    qid = body.question_id or s.question_id
    if qid not in answered:
        raise ApiError("INVALID_QUESTION", "Only a question you have already answered can be explained.", 422)
    return ok({"session_id": s.id, **explanation_service.explain(db, db.get(Question, qid), body.level, s.attempt if qid == s.question_id else None)})


@router.post("/{session_id}/reasoning", response_model=Envelope, summary="Add the student's own explanation as evidence")
def reasoning(session_id: str, body: ReasoningRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Read by Groq when configured, otherwise by phrase matching. Either way it is light evidence: the follow-up remains the real test."""
    s = own_session(db, user, session_id)
    diagnostic_service.add_reasoning(db, user, s, body.reasoning)
    db.commit()
    return ok(diagnostic_service.view(db, s))


@router.post("/{session_id}/followup", response_model=Envelope, summary="Get the discriminating follow-up question", responses={409: {"description": "DIAGNOSTIC_CLOSED"}})
def followup(session_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """
    Chooses the question whose answer the competing hypotheses disagree about most (highest expected
    information gain) and stores why it was chosen. Calling it again before answering returns the same question.
    If nothing useful is left to ask, the diagnosis is concluded and returned instead.
    """
    s = own_session(db, user, session_id)
    f = diagnostic_service.next_followup(db, user, s)
    db.commit()
    if f is None:
        return ok({"session_id": s.id, "question": None, "purpose": None, "options": [], "diagnostic": diagnostic_service.view(db, s)})
    return ok(diagnostic_service.followup_view(db, f))


@router.post("/{session_id}/evaluate-followup", response_model=Envelope, summary="Answer the follow-up and re-evaluate",
             responses={409: {"description": "FOLLOWUP_NOT_REQUESTED"}, 422: {"description": "INVALID_OPTION"}})
def evaluate_followup(session_id: str, body: FollowUpAnswer, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """
    Updates the confidence with the new evidence. A diagnosis is stated only when one explanation is
    above the threshold (more than 70%); otherwise `followup.required` stays true, or the result is UNCERTAIN.
    """
    s = own_session(db, user, session_id)
    unlocked = diagnostic_service.evaluate_followup(db, user, s, body.answer, body.reasoning)
    db.commit()
    return ok({**diagnostic_service.view(db, s), "unlocked": unlocked})
