from sqlalchemy.orm import Session

from ..core.errors import ApiError, not_found
from ..models import DiagnosticSession, Question, StudyMaterial, User

# documented on every protected route
AUTH_ERRORS = {401: {"description": "UNAUTHORIZED: missing or expired token"}}


def own_material(db: Session, user: User, material_id: str) -> StudyMaterial:
    m = db.get(StudyMaterial, material_id)
    if not m:
        raise not_found("study_material")
    if m.user_id != user.id:
        raise ApiError("FORBIDDEN", "This material belongs to another account.", 403)
    return m


def visible_question(db: Session, user: User, question_id: str) -> Question:
    """Bank questions are shared; generated ones are visible only to the student they were written for."""
    q = db.get(Question, question_id)
    if not q:
        raise not_found("question")
    if q.owner_id not in (None, user.id):
        raise ApiError("FORBIDDEN", "This question belongs to another account.", 403)
    return q


def own_session(db: Session, user: User, session_id: str, what: str = "diagnostic") -> DiagnosticSession:
    s = db.get(DiagnosticSession, session_id)
    if not s:
        raise not_found(what)
    if s.user_id != user.id:
        raise ApiError("FORBIDDEN", "This record belongs to another account.", 403)
    return s
