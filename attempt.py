from sqlalchemy import JSON, Boolean, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .base import Timestamps, new_id


class Attempt(Base, Timestamps):
    """One answer (or skip). Attempts are history: they are added, never overwritten."""

    __tablename__ = "attempts"
    # the same submission sent twice resolves to the same row, so it cannot be rewarded twice
    __table_args__ = (UniqueConstraint("user_id", "client_key", name="uq_attempt_client_key"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    client_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_option: Mapped[str | None] = mapped_column(String(2), nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    marks_awarded: Mapped[float] = mapped_column(Float, default=0)
    total_marks: Mapped[float] = mapped_column(Float, default=1)
    percentage: Mapped[float] = mapped_column(Float, default=0)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    evaluation: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    user = relationship("User", back_populates="attempts")
    question = relationship("Question", back_populates="attempts")
    session = relationship("DiagnosticSession", back_populates="attempt", uselist=False, cascade="all, delete-orphan")
