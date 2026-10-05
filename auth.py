import re
import secrets
from datetime import timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.errors import ApiError, ok
from ..core.security import create_token, current_user, hash_password, verify_password
from ..core.config import get_settings
from ..models import PasswordReset, User
from ..models.base import now
from ..schemas.requests import Envelope, ForgotPasswordRequest, LoginRequest, RegisterRequest, ResetPasswordRequest
from ..services import email_service, personalization_service
from .deps import AUTH_ERRORS

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _session(db: Session, user: User) -> dict:
    return {"token": create_token(user.id), "token_type": "bearer", "user": personalization_service.profile(db, user)["user"]}


@router.post("/register", response_model=Envelope, status_code=201, summary="Create an account", responses={409: {"description": "EMAIL_TAKEN"}})
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """Creates the account and signs it in. The name defaults to the part of the email before the @."""
    if db.scalar(select(User.id).where(User.email == body.email)):
        raise ApiError("EMAIL_TAKEN", "An account with this Study ID already exists. Sign in instead.", 409)
    local = re.sub(r"[._-]+", " ", body.email.split("@")[0]).strip()
    user = User(email=body.email, password_hash=hash_password(body.password), name=(body.name or local.title() or "Student")[:80], beliefs={}, cursors={})
    db.add(user)
    db.commit()
    return ok(_session(db, user))


@router.post("/login", response_model=Envelope, summary="Sign in", responses={401: {"description": "INVALID_CREDENTIALS"}})
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email))
    # one message for both cases, so the response does not reveal which emails have accounts
    if not user or not verify_password(body.password, user.password_hash):
        raise ApiError("INVALID_CREDENTIALS", "That Study ID and Secret Squeak do not match.", 401)
    return ok(_session(db, user))


@router.get("/me", response_model=Envelope, summary="The signed-in user", responses=AUTH_ERRORS)
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return ok(personalization_service.profile(db, user)["user"])


RESET_COOLDOWN_SECONDS = 60
RESET_MAX_TRIES = 5


def _aware(t):
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)  # SQLite hands datetimes back without a zone


@router.post("/forgot-password", response_model=Envelope, summary="Email a reset code for a forgotten Secret Squeak", responses={503: {"description": "EMAIL_NOT_CONFIGURED"}, 502: {"description": "EMAIL_FAILED"}})
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Sends a 6-digit code (and a link carrying it) to the Study ID, if it has an account. The reply is the same
    either way, so it does not reveal which emails are registered. The code works once, for a limited time.
    """
    s = get_settings()
    if not email_service.configured():
        raise ApiError("EMAIL_NOT_CONFIGURED", "Email is not set up on this server yet, so reset codes cannot be sent. Add the SMTP settings to backend/.env.", 503)
    reply = {"sent": True, "expires_in_minutes": s.reset_code_minutes, "message": "If that Study ID has an account, a 6-digit code is on its way to its inbox."}
    user = db.scalar(select(User).where(User.email == body.email))
    if not user:
        return ok(reply)
    last = db.scalar(select(PasswordReset).where(PasswordReset.user_id == user.id).order_by(PasswordReset.created_at.desc()))
    if last and not last.used and (now() - _aware(last.created_at)).total_seconds() < RESET_COOLDOWN_SECONDS:
        return ok(reply)  # one was sent a moment ago; no flood of emails

    code = f"{secrets.randbelow(10**6):06d}"
    for old in db.scalars(select(PasswordReset).where(PasswordReset.user_id == user.id, PasswordReset.used.is_(False))):
        old.used = True  # only the newest code works
    row = PasswordReset(user_id=user.id, code_hash=hash_password(code), expires_at=now() + timedelta(minutes=s.reset_code_minutes))
    db.add(row)
    db.flush()
    link = f"{s.origins[0].rstrip('/')}/#/login?reset={user.email}&code={code}"
    subject, text, html = email_service.reset_email(user.name, code, link, s.reset_code_minutes)
    try:
        email_service.send(user.email, subject, text, html)
    except ApiError:
        db.rollback()  # a code nobody received must not linger
        raise
    db.commit()
    return ok(reply)


@router.post("/reset-password", response_model=Envelope, summary="Set a new Secret Squeak with the emailed code", responses={400: {"description": "INVALID_RESET_CODE"}})
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    """On success the new Secret Squeak is saved, the code is spent, and the account is signed in."""
    bad = ApiError("INVALID_RESET_CODE", "That code is wrong or has expired. Ask for a new one.", 400)
    user = db.scalar(select(User).where(User.email == body.email))
    row = db.scalar(select(PasswordReset).where(PasswordReset.user_id == user.id, PasswordReset.used.is_(False)).order_by(PasswordReset.created_at.desc())) if user else None
    if not row or _aware(row.expires_at) < now():
        raise bad
    if not verify_password(body.code, row.code_hash):
        row.attempts += 1
        if row.attempts >= RESET_MAX_TRIES:
            row.used = True  # too many guesses: this code is finished
        db.commit()
        raise bad
    row.used = True
    user.password_hash = hash_password(body.password)
    db.commit()
    return ok(_session(db, user))
