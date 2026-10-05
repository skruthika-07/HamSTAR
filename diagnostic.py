from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .base import Timestamps, new_id, now

# ANALYZING → FOLLOWUP_REQUIRED → SUPPORTED | UNCERTAIN → CORRECTED
STATUSES = ("ANALYZING", "FOLLOWUP_REQUIRED", "SUPPORTED", "UNCERTAIN", "CORRECTED")
# the four categories a mistake is classified into (stored in final_diagnosis and mistake_logs.mistake_type)
DIAGNOSES = ("MISCONCEPTION", "CARELESS_SLIP", "GAP_IN_UNDERSTANDING", "CALCULATION_ERROR")
HYPOTHESES = DIAGNOSES


class DiagnosticSession(Base, Timestamps):
    """The investigation of one wrong answer. Once it has a final diagnosis it is also the 'past mistake' record."""

    __tablename__ = "diagnostic_sessions"
    __table_args__ = (CheckConstraint("final_diagnosis IS NULL OR final_diagnosis IN ('MISCONCEPTION', 'CARELESS_SLIP', 'GAP_IN_UNDERSTANDING', 'CALCULATION_ERROR')", name="ck_diagnosis_category"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"), unique=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    topic: Mapped[str] = mapped_column(String(80), index=True)
    selected_option: Mapped[str] = mapped_column(String(2))

    # probability over hypotheses, before the wrong answer and now
    belief_before: Mapped[dict] = mapped_column(JSON, default=dict)
    belief: Mapped[dict] = mapped_column(JSON, default=dict)
    initial: Mapped[dict] = mapped_column(JSON, default=dict)
    final: Mapped[dict] = mapped_column(JSON, default=dict)
    # [{question_id, selected, before, after, gain, purpose}]
    steps: Mapped[list] = mapped_column(JSON, default=list)

    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning_evidence: Mapped[list] = mapped_column(JSON, default=list)
    # slip sub-type suggested by the student's own words: CALCULATION_ERROR | MISINTERPRETATION | None
    slip_kind: Mapped[str | None] = mapped_column(String(30), nullable=True)

    primary_hypothesis: Mapped[str | None] = mapped_column(String(30), nullable=True)
    alternative_hypotheses: Mapped[list] = mapped_column(JSON, default=list)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    initial_confidence: Mapped[float] = mapped_column(Float, default=0)
    followup_question_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    followup_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_diagnosis: Mapped[str | None] = mapped_column(String(30), nullable=True)
    misconception_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    final_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ANALYZING", index=True)
    feedback: Mapped[str] = mapped_column(Text, default="")

    # retest after targeted help
    retry: Mapped[list] = mapped_column(JSON, default=list)
    understanding: Mapped[float | None] = mapped_column(Float, nullable=True)
    corrected: Mapped[bool] = mapped_column(Boolean, default=False)
    prompt_version: Mapped[str | None] = mapped_column(String(60), nullable=True)

    user = relationship("User", back_populates="sessions")
    attempt = relationship("Attempt", back_populates="session")
    question = relationship("Question")
    followups = relationship("FollowUpQuestion", back_populates="session", cascade="all, delete-orphan", order_by="FollowUpQuestion.created_at")


class FollowUpQuestion(Base):
    """A question asked because the competing hypotheses expect different answers to it."""

    __tablename__ = "followup_questions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    diagnostic_session_id: Mapped[str] = mapped_column(ForeignKey("diagnostic_sessions.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    question: Mapped[str] = mapped_column(Text)
    purpose: Mapped[str] = mapped_column(Text)
    hypothesis_a: Mapped[str] = mapped_column(String(120))
    hypothesis_b: Mapped[str] = mapped_column(String(120))
    expected_signal_a: Mapped[str] = mapped_column(Text)
    expected_signal_b: Mapped[str] = mapped_column(Text)
    # bank = verified probe chosen by information gain; groq = written for this session
    source: Mapped[str] = mapped_column(String(10), default="bank")
    gain: Mapped[float] = mapped_column(Float, default=0)
    response: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    session = relationship("DiagnosticSession", back_populates="followups")
