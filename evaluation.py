from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.errors import ok
from ..core.security import current_user
from ..models import EvaluationRun, User
from ..schemas.requests import Envelope, EvaluationRunRequest
from ..services import evaluation_service
from .deps import AUTH_ERRORS

router = APIRouter(prefix="/api/evaluation", tags=["Evaluation lab"], responses=AUTH_ERRORS)


def _view(run: EvaluationRun) -> dict:
    return {"id": run.id, "created_at": run.created_at.isoformat(), **run.results}


@router.post("/run", response_model=Envelope, status_code=201, summary="Run the simulated-student evaluation")
def run(body: EvaluationRunRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """
    Simulated students with an injected cause (misconception, careless slips, unmodelled gap) are run through
    the diagnostic engine under three follow-up policies. Returns precision, recall, F1, the slip
    false-positive rate, calibration and follow-up discrimination, plus five worked cases
    (misconception, careless slip, calculation error, misinterpretation, strong understanding).
    Nothing is hard-coded: a different seed gives different students and different figures.
    """
    return ok(_view(evaluation_service.run(db, user, body.students, body.seed)))


@router.get("/results", response_model=Envelope, summary="The most recent evaluation run")
def results(user: User = Depends(current_user), db: Session = Depends(get_db)):
    last = db.scalar(select(EvaluationRun).where(EvaluationRun.user_id == user.id).order_by(EvaluationRun.created_at.desc()))
    return ok(_view(last) if last else None)
