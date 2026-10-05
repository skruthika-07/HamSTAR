from datetime import timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.errors import ApiError, ok
from ..core.security import current_user
from ..models import Task, User
from ..schemas.requests import Envelope, TaskCreate, TaskPatch
from ..services import email_service
from .deps import AUTH_ERRORS

router = APIRouter(prefix="/api/tasks", tags=["Tasks and reminders"], responses=AUTH_ERRORS)


def _utc(t):
    if t is None:
        return None
    return t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t.astimezone(timezone.utc)


def _view(t: Task) -> dict:
    return {"id": t.id, "title": t.title, "topic": t.topic, "done": t.done, "starred": t.starred, "deadline": _utc(t.deadline).isoformat() if t.deadline else None, "reminder_sent": t.reminder_sent, "created_at": _utc(t.created_at).isoformat() if t.created_at else None}


def _own(db: Session, user: User, task_id: str) -> Task:
    t = db.get(Task, task_id)
    if not t or t.user_id != user.id:
        raise ApiError("TASK_NOT_FOUND", "That task was not found.", 404)
    return t


@router.get("", response_model=Envelope, summary="Your tasks")
def listing(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """`reminders` says whether reminder emails can be sent (they need the SMTP settings)."""
    rows = db.scalars(select(Task).where(Task.user_id == user.id).order_by(Task.created_at)).all()
    return ok({"tasks": [_view(t) for t in rows], "reminders": email_service.configured()})


@router.post("", response_model=Envelope, status_code=201, summary="Add a task, with an optional deadline")
def create(body: TaskCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """
    With a `deadline`, one reminder email goes to your Study ID 24 hours before it, unless the task is marked done
    by then. A task without a deadline never gets an email.
    """
    t = Task(user_id=user.id, title=body.title.strip(), topic=body.topic.strip() or "General", starred=body.starred, deadline=_utc(body.deadline))
    db.add(t)
    db.commit()
    return ok(_view(t))


@router.patch("/{task_id}", response_model=Envelope, summary="Change a task: done, star, title, folder or deadline", responses={404: {"description": "TASK_NOT_FOUND"}})
def patch(task_id: str, body: TaskPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Changing the deadline arms the reminder again for the new date. Send `deadline: null` to remove it."""
    t = _own(db, user, task_id)
    sent = body.model_fields_set
    for field in ("title", "topic", "done", "starred"):
        if field in sent and getattr(body, field) is not None:
            value = getattr(body, field)
            setattr(t, field, value.strip() if isinstance(value, str) else value)
    if "deadline" in sent:
        new = _utc(body.deadline)
        if new != _utc(t.deadline):
            t.deadline, t.reminder_sent = new, False
    db.commit()
    return ok(_view(t))


@router.delete("/{task_id}", response_model=Envelope, summary="Delete a task", responses={404: {"description": "TASK_NOT_FOUND"}})
def delete(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(_own(db, user, task_id))
    db.commit()
    return ok({"deleted": task_id})
