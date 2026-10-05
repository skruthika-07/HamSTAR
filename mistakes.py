from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.errors import ok
from ..core.security import current_user
from ..models import DiagnosticSession, User
from ..schemas.requests import Envelope, RetryAnswer
from ..services import diagnostic_service, personalization_service
from .deps import AUTH_ERRORS, own_session

router = APIRouter(prefix="/api/mistakes", tags=["Past mistakes"], responses=AUTH_ERRORS)
NOT_FOUND = {404: {"description": "MISTAKE_NOT_FOUND"}, 403: {"description": "FORBIDDEN"}}


@router.get("", response_model=Envelope, summary="Your diagnosed mistakes, newest first")
def list_mistakes(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Statuses: NEEDS_REVIEW, MISCONCEPTION_IDENTIFIED, SLIP_IDENTIFIED, CORRECTED. `retry_order` lists the unresolved ones in the order worth retrying."""
    rows = db.scalars(select(DiagnosticSession).where(DiagnosticSession.user_id == user.id, DiagnosticSession.final_diagnosis.is_not(None)).order_by(DiagnosticSession.created_at.desc())).all()
    return ok({"mistakes": [diagnostic_service.mistake_view(db, s) for s in rows], "retry_order": [s.id for s in personalization_service.retry_queue(db, user)]})


@router.get("/{mistake_id}", response_model=Envelope, summary="One mistake", responses=NOT_FOUND)
def get_mistake(mistake_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return ok(diagnostic_service.mistake_view(db, own_session(db, user, mistake_id, "mistake")))


@router.post("/{mistake_id}/retry", response_model=Envelope, summary="Start (or continue) a retry: targeted help and a retest question", responses=NOT_FOUND)
def retry(mistake_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The retest is a different question on the same idea wherever the bank has one."""
    return ok(diagnostic_service.retry_start(db, user, own_session(db, user, mistake_id, "mistake")))


@router.post("/{mistake_id}/retry/evaluate", response_model=Envelope, summary="Answer the retest question", responses={**NOT_FOUND, 409: {"description": "INVALID_QUESTION"}})
def retry_evaluate(mistake_id: str, body: RetryAnswer, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The mistake becomes CORRECTED only if understanding, judged on this answer, is above the threshold (more than 70%)."""
    s = own_session(db, user, mistake_id, "mistake")
    result = diagnostic_service.retry_evaluate(db, user, s, body.question_id, body.selected_option.strip().upper())
    db.commit()
    return ok(result)
