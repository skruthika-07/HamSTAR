"""
Task reminders. Once an hour a background job looks for tasks that are not done, have a deadline within the
next 24 hours and have not had their reminder yet, and emails the student once. A task that is completed in
time, or has no deadline, never gets an email.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.database import SessionLocal
from ..core.errors import ApiError
from ..core.logging import log
from ..models import Task, User
from ..models.base import now
from . import email_service

WINDOW = timedelta(hours=24)


def aware(t: datetime) -> datetime:
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)  # SQLite hands datetimes back without a zone


def due(db: Session, at: datetime | None = None) -> list[Task]:
    at = at or now()
    rows = db.scalars(select(Task).where(Task.done.is_(False), Task.reminder_sent.is_(False), Task.deadline.is_not(None))).all()
    return [t for t in rows if at < aware(t.deadline) <= at + WINDOW]


def reminder_email(name: str, title: str, deadline: datetime, link: str) -> tuple[str, str, str]:
    when = aware(deadline).strftime("%A %d %B, %H:%M UTC")
    subject = f"⏰ HamSTAR Reminder: {title} is due tomorrow!"
    text = (
        f"Hi {name},\n\nA little squeak from your study hamster: your task \"{title}\" is due soon ({when}).\n\n"
        f"You still have time. A few focused minutes today and it is done!\nOpen your tasks: {link}\n\n"
        "Small steps, big dreams.\nHamSTAR"
    )
    html = f"""<div style="font-family:Segoe UI,Arial,sans-serif;max-width:480px;margin:auto;padding:24px;background:#fdf6e3;border-radius:16px;color:#46291b">
<h2 style="margin:0 0 8px">Squeak! A deadline is coming up</h2>
<p>Hi {name}, a little nudge from your study hamster.</p>
<p style="font-size:18px;font-weight:800;background:#fbe3a1;border-radius:12px;padding:12px">{title}</p>
<p>It is due <b>{when}</b>. You still have time: a few focused minutes today and it is done!</p>
<p><a href="{link}" style="display:inline-block;background:#f0b93a;color:#46291b;font-weight:700;padding:10px 18px;border-radius:999px;text-decoration:none">Open my tasks</a></p>
<p style="color:#8a7560;font-size:13px">You get one reminder per task. Mark it done and I will stay quiet.</p>
<p style="color:#8a7560;font-size:13px">Small steps, big dreams — HamSTAR</p></div>"""
    return subject, text, html


def send_due(db: Session, at: datetime | None = None) -> int:
    """Send the reminders that are due. Each task is marked as it is sent, so it can never get a second one."""
    if not email_service.configured():
        return 0
    link = f"{get_settings().origins[0].rstrip('/')}/#/tasks"
    sent = 0
    for task in due(db, at):
        user = db.get(User, task.user_id)
        if not user:
            continue
        subject, text, html = reminder_email(user.name, task.title, task.deadline, link)
        try:
            email_service.send(user.email, subject, text, html)
        except ApiError:
            continue  # left unsent: the next hourly run tries again
        task.reminder_sent = True
        db.commit()
        sent += 1
    return sent


def _job() -> None:
    try:
        with SessionLocal() as db:
            n = send_due(db)
        if n:
            log.info("Task reminders sent: %s", n)
    except Exception:  # noqa: BLE001 - a failed run must not stop the scheduler
        log.exception("The task reminder job failed")


def start():
    """Start the hourly job. Returns the scheduler (to shut down on exit), or None when reminders are off."""
    if not get_settings().reminders_enabled:
        return None
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        log.warning("APScheduler is not installed, so task reminder emails are off. Run: pip install -r requirements.txt")
        return None
    scheduler = BackgroundScheduler(timezone="UTC")
    # hourly, and once shortly after start so a restart does not delay a reminder by an hour
    scheduler.add_job(_job, "interval", hours=1, next_run_time=now() + timedelta(seconds=30), id="task-reminders", max_instances=1, coalesce=True)
    scheduler.start()
    log.info("Task reminders: checking every hour%s.", "" if email_service.configured() else " (email is not configured yet, so nothing will be sent)")
    return scheduler
