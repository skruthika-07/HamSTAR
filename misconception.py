from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import now


class Misconception(Base):
    """A reusable faulty rule. New ones can be added as rows; nothing about them is hard-wired in code."""

    __tablename__ = "misconceptions"

    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    topic: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    # regular expressions that, found in a student's explanation, point to this rule
    indicators: Mapped[list] = mapped_column(JSON, default=list)
    # [{question_id, option_id, text}]
    common_wrong_options: Mapped[list] = mapped_column(JSON, default=list)
    # {explanation: [...], worked_example}
    remediation: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
