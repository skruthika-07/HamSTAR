from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import Timestamps, new_id, now


class PasswordReset(Base):
    """One emailed reset code. Only its hash is stored; it works once and for a short time."""

    __tablename__ = "password_resets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    code_hash: Mapped[str] = mapped_column(String(100))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # wrong codes tried against this reset
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class MistakeLog(Base):
    """
    One wrong answer: what it was about, what kind of mistake it looks like, and where it came from.
    The same concept turning up twice or more (and not yet put right) is a recurring mistake.
    """

    __tablename__ = "mistake_logs"
    __table_args__ = (CheckConstraint("mistake_type IN ('MISCONCEPTION', 'CARELESS_SLIP', 'GAP_IN_UNDERSTANDING', 'CALCULATION_ERROR')", name="ck_mistake_category"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"), unique=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    concept: Mapped[str] = mapped_column(String(120))
    # the concept in lower case, for grouping
    concept_key: Mapped[str] = mapped_column(String(120), index=True)
    # the document it came from: a starter folder id, or "material:<id>"
    document: Mapped[str] = mapped_column(String(60), index=True)
    folder: Mapped[str] = mapped_column(String(80), default="")
    parent: Mapped[str] = mapped_column(String(80), default="")
    # CARELESS_SLIP | MISCONCEPTION | GAP_IN_UNDERSTANDING | CALCULATION_ERROR
    mistake_type: Mapped[str] = mapped_column(String(30), index=True)
    # correct answers on this concept since the mistake; two of them put it right
    fixes: Mapped[int] = mapped_column(Integer, default=0)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class Note(Base, Timestamps):
    """Revision notes generated from an uploaded file, kept for the student who made them."""

    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    file_name: Mapped[str] = mapped_column(String(200))
    # the notes as structured sections (see schemas.ai.GeneratedNotes) and as markdown
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    markdown: Mapped[str] = mapped_column(Text, default="")


class Task(Base, Timestamps):
    """A study task. With a deadline it gets one reminder email, 24 hours before, unless it is done by then."""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    # the folder it is filed under (any name)
    topic: Mapped[str] = mapped_column(String(80), default="General")
    done: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    starred: Mapped[bool] = mapped_column(Boolean, default=False)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    # set when the reminder email has gone out, so a task never gets two
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)


class AnswerImage(Base, Timestamps):
    """A photo a student sent with an answer (working, a diagram, a solution). Stored as it is; never read by OCR or AI."""

    __tablename__ = "answer_images"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # set once the answer it came with has been submitted
    attempt_id: Mapped[str | None] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"), nullable=True, index=True)
    file_path: Mapped[str] = mapped_column(String(400))
    file_name: Mapped[str] = mapped_column(String(200), default="photo")
    mime: Mapped[str] = mapped_column(String(40))
    file_size: Mapped[int] = mapped_column(Integer, default=0)
