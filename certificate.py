from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .base import new_id, now


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    # human-readable number printed on the certificate
    code: Mapped[str] = mapped_column(String(20))
    unlocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    certificate_url: Mapped[str] = mapped_column(String(200), default="")
    share_token: Mapped[str] = mapped_column(String(32), default=new_id, unique=True)

    user = relationship("User", back_populates="certificate")
