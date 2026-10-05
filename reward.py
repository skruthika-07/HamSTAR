from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .base import new_id, now


class Reward(Base):
    """Ledger of everything earned. The unique key is what makes rewards idempotent."""

    __tablename__ = "rewards"
    __table_args__ = (UniqueConstraint("user_id", "kind", "ref", name="uq_reward_once"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # TIARA (ref = attempt id) | CORRECTION (ref = diagnostic session id) | DEMO
    kind: Mapped[str] = mapped_column(String(20))
    ref: Mapped[str] = mapped_column(String(64))
    amount: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    user = relationship("User", back_populates="rewards")
