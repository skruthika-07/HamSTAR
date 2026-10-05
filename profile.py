from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.errors import ok
from ..core.security import current_user
from ..models import User
from ..schemas.requests import DemoRequest, Envelope, ProfilePatch
from ..services import demo_service, personalization_service
from .deps import AUTH_ERRORS

router = APIRouter(prefix="/api", tags=["Profile"], responses=AUTH_ERRORS)


@router.get("/profile", response_model=Envelope, summary="Your profile: hamster, Tiara, streaks, badges, certificate, progress")
def get_profile(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return ok(personalization_service.profile(db, user))


@router.patch("/profile", response_model=Envelope, summary="Change your name, role or hamster")
def patch_profile(body: ProfilePatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    for field in ("name", "role", "avatar"):
        value = getattr(body, field)
        if value is not None:
            setattr(user, field, value.strip() if isinstance(value, str) else value)
    db.commit()
    return ok(personalization_service.profile(db, user))


@router.post("/demo", response_model=Envelope, summary="Demo helpers for the signed-in account")
def demo(body: DemoRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """`load` fills the account with a demo history produced by the real diagnosis flow, `reset` empties it, `add_tiara` adds Tiara (to show the certificate unlocking)."""
    unlocked = demo_service.run(db, user, body.action, body.amount)
    return ok({"action": body.action, "unlocked": unlocked})
