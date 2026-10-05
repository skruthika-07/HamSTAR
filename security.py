from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..models import User
from .config import get_settings
from .database import get_db
from .errors import ApiError

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], hashed.encode())
    except ValueError:
        return False


def create_token(user_id: str) -> str:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(minutes=s.jwt_expire_minutes)
    return jwt.encode({"sub": user_id, "exp": exp}, s.jwt_secret, algorithm=s.jwt_algorithm)


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    """Every protected route depends on this; all queries are then scoped to the returned user."""
    if not creds:
        raise ApiError("UNAUTHORIZED", "Sign in to continue.", 401)
    s = get_settings()
    try:
        payload = jwt.decode(creds.credentials, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except jwt.PyJWTError:
        raise ApiError("UNAUTHORIZED", "Your session has expired. Sign in again.", 401)
    user = db.get(User, payload.get("sub"))
    if not user:
        raise ApiError("UNAUTHORIZED", "Account not found.", 401)
    return user
