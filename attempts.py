from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.errors import ok
from ..core.security import current_user
from ..models import Attempt, Question, User
from ..core.errors import not_found
from ..core.errors import ApiError
from ..schemas.requests import AttemptFollowUpAnswer, AttemptRequest, EvaluateRequest, Envelope, ExplainRequest
from ..services import answer_evaluation_service, answer_image_service, explanation_service, followup_service, verification_service
from .deps import AUTH_ERRORS, visible_question

router = APIRouter(prefix="/api/attempts", tags=["Attempts"], responses=AUTH_ERRORS)


@router.post("/evaluate", response_model=Envelope, summary="Submit an answer for evaluation",
             responses={404: {"description": "QUESTION_NOT_FOUND"}, 422: {"description": "INVALID_OPTION or EMPTY_ANSWER"}, 503: {"description": "AI_PROVIDER_ERROR"}})
def evaluate(body: EvaluateRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """
    The evaluation depends on the question type.

    **MCQ, correct**: +1 Tiara, streak updated, no diagnostic session.
    **MCQ, wrong**: the chosen option is kept as evidence and a diagnostic session opens with competing
    hypotheses. Nothing is called a misconception at this point and the answer is not revealed.
    **Fill in the blank**: compared with the expected and accepted answers, then semantically by Groq.
    **Short / long answer**: marked by Groq against the rubric.

    Send `client_key` (any unique string per submission): a repeated request then returns the
    original result and awards nothing twice. Send `image_id` (from `/api/answer-images`) to store a photo of the
    working with the answer; it is shown beside the answer and is not marked.
    """
    question = visible_question(db, user, body.question_id)
    if body.image_id:
        answer_image_service.check(db, user, body.image_id, body.client_key)  # before anything is marked or awarded
    verification_service.ensure(db, question)  # never mark against a maths answer key that has not been checked
    result = answer_evaluation_service.evaluate(db, user, question, body.answer, body.selected_option, body.reasoning, body.client_key, body.practice)
    if body.image_id:
        # the photo is kept with the answer as it is, for reference: it is not read or marked
        result["image"] = answer_image_service.attach(db, user, body.image_id, result["attempt_id"])
    return ok(result)


@router.post("", response_model=Envelope, status_code=201, summary="Skip a question", responses={404: {"description": "QUESTION_NOT_FOUND"}})
def skip(body: AttemptRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """A skip earns nothing and is not a mistake. It resets the correct-answer streak and the no-skip run."""
    question = visible_question(db, user, body.question_id)
    return ok(answer_evaluation_service.skip(db, user, question, body.client_key, body.practice))


def _own_attempt(db: Session, user: User, attempt_id: str) -> Attempt:
    attempt = db.get(Attempt, attempt_id)
    if not attempt or attempt.user_id != user.id or attempt.skipped:
        raise not_found("attempt")
    return attempt


@router.post("/{attempt_id}/explain", response_model=Envelope, summary="The correct answer, explained (again, more simply, on request)", responses={404: {"description": "ATTEMPT_NOT_FOUND"}})
def explain(attempt_id: str, body: ExplainRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """
    For any answered question. `level` 0 is a clean explanation of the correct answer; each higher level
    re-explains the same idea in simpler words with an everyday example. For a wrong answer the response also carries
    `mistake_type`: the kind of mistake it most looks like (careless slip, misconception, incomplete understanding,
    calculation error).
    """
    attempt = _own_attempt(db, user, attempt_id)
    qid = body.question_id or attempt.question_id
    if qid != attempt.question_id and qid not in followup_service.question_ids(attempt):
        raise ApiError("INVALID_QUESTION", "Only a question you have already answered can be explained.", 422)
    return ok(explanation_service.explain(db, db.get(Question, qid), body.level, attempt if qid == attempt.question_id else None))


@router.post("/{attempt_id}/followup", response_model=Envelope, summary="A follow-up question on the same concept (written answers)",
             responses={404: {"description": "ATTEMPT_NOT_FOUND"}, 409: {"description": "NO_MORE_FOLLOWUPS"}, 503: {"description": "AI_PROVIDER_ERROR"}})
def followup(attempt_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """
    For a wrong one-word, fill-in-the-blank, brief or detailed answer, after \"I understood\": Groq writes a new
    multiple-choice question on the same concept, slightly different from the original. At most two per answer;
    the second is easier. (Wrong multiple-choice answers use `/api/diagnostics/{id}/followup` instead.)
    """
    return ok(followup_service.next_followup(db, user, _own_attempt(db, user, attempt_id)))


@router.post("/{attempt_id}/followup/evaluate", response_model=Envelope, summary="Answer that follow-up question", responses={404: {"description": "ATTEMPT_NOT_FOUND"}, 409: {"description": "INVALID_QUESTION"}})
def followup_evaluate(attempt_id: str, body: AttemptFollowUpAnswer, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Returns whether it was right, the question with its answer, and whether one more follow-up is available."""
    return ok(followup_service.evaluate_followup(db, user, _own_attempt(db, user, attempt_id), body.question_id, body.selected_option.strip().upper()))


@router.get("/history", response_model=Envelope, summary="Your past attempts, newest first")
def history(limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(Attempt, Question).join(Question, Question.id == Attempt.question_id).where(Attempt.user_id == user.id).order_by(Attempt.created_at.desc()).limit(limit).offset(offset)).all()
    return ok([
        {"id": a.id, "question_id": q.id, "question": q.question_text, "topic": q.topic, "question_type": q.question_type, "selected_option": a.selected_option, "answer": a.answer,
         "is_correct": a.is_correct, "skipped": a.skipped, "marks_awarded": a.marks_awarded, "total_marks": a.total_marks, "percentage": a.percentage, "image": (a.evaluation or {}).get("image"), "created_at": a.created_at.isoformat()}
        for a, q in rows
    ])
