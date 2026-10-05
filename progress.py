from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.errors import ok
from ..core.security import current_user
from ..models import User
from ..schemas.requests import Envelope
from ..services import personalization_service
from .deps import AUTH_ERRORS

router = APIRouter(prefix="/api", tags=["Dashboard and progress"], responses=AUTH_ERRORS)


@router.get("/dashboard", response_model=Envelope, summary="Everything the dashboard shows, in one call")
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """User, Tiara, streaks, totals, progress per folder, recent mistakes and activity, badges, certificate, recommendations, materials."""
    return ok(personalization_service.dashboard(db, user))


@router.get("/progress", response_model=Envelope, summary="Confidence per folder and per concept")
def progress(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return ok(personalization_service.progress(db, user))


@router.get("/learning/recommendations", response_model=Envelope, summary="What to practise next, from your own history")
def recommendations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Built from unresolved misconceptions, low-confidence concepts, repeated and recent mistakes, and weak topics."""
    return ok(personalization_service.recommendations(db, user))
