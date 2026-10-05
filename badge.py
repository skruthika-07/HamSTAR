from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .base import new_id, now

# code → (name, requirement, target)
BADGES = {
    "streak": ("Perfect Paw Streak", "10 correct answers in a row", 10),
    "noskip": ("No-Skip Scholar", "25 questions in a row without skipping", 25),
    "mistakes": ("Mistake Master", "50 mistakes corrected (understanding above 70%)", 50),
}


class Badge(Base):
    __tablename__ = "badges"
    __table_args__ = (UniqueConstraint("user_id", "code", name="uq_badge_once"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    unlocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    user = relationship("User", back_populates="badges")
