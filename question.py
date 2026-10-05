from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .base import new_id, now

QUESTION_TYPES = ("ONE_WORD", "FILL_BLANK", "MCQ", "SHORT_ANSWER", "LONG_ANSWER")
# marks allowed for each type, inclusive
MARK_RULES = {"ONE_WORD": (1, 1), "MCQ": (1, 1), "FILL_BLANK": (1, 2), "SHORT_ANSWER": (4, 8), "LONG_ANSWER": (12, 20)}


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_id)
    study_material_id: Mapped[str | None] = mapped_column(ForeignKey("study_materials.id", ondelete="CASCADE"), nullable=True, index=True)
    # null for the shared verified bank; set for questions generated for one student
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    topic: Mapped[str] = mapped_column(String(80), index=True)
    # main = learning question, probe = discriminating follow-up
    role: Mapped[str] = mapped_column(String(10), default="main")
    question_type: Mapped[str] = mapped_column(String(20), default="MCQ")
    question_text: Mapped[str] = mapped_column(Text)
    marks: Mapped[int] = mapped_column(Integer, default=1)
    difficulty: Mapped[str] = mapped_column(String(10), default="medium")
    # MCQ: [{id, text, correct, misconception, reasoning, slip_weight}]
    options: Mapped[list] = mapped_column(JSON, default=list)
    correct_option: Mapped[str | None] = mapped_column(String(2), nullable=True)
    expected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    accepted_answers: Mapped[list] = mapped_column(JSON, default=list)
    model_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    rubric: Mapped[list] = mapped_column(JSON, default=list)
    explanation: Mapped[str] = mapped_column(Text, default="")
    source_context: Mapped[str] = mapped_column(Text, default="")
    # {targets, expected_concepts, key_points, prompt_version, position}
    diagnostic_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)

    material = relationship("StudyMaterial", back_populates="questions")
    attempts = relationship("Attempt", back_populates="question")
