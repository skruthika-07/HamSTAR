from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .base import Timestamps, new_id


class User(Base, Timestamps):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(80), default="Student")
    avatar: Mapped[str] = mapped_column(String(20), default="reader")

    tiara_count: Mapped[int] = mapped_column(Integer, default=0)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    # questions completed in a row without skipping
    noskip_count: Mapped[int] = mapped_column(Integer, default=0)
    answered_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    mistakes_corrected: Mapped[int] = mapped_column(Integer, default=0)

    # per-topic probability over hypotheses, and the position in each topic's question list
    beliefs: Mapped[dict] = mapped_column(JSON, default=dict)
    cursors: Mapped[dict] = mapped_column(JSON, default=dict)

    materials = relationship("StudyMaterial", back_populates="user", cascade="all, delete-orphan")
    attempts = relationship("Attempt", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("DiagnosticSession", back_populates="user", cascade="all, delete-orphan")
    rewards = relationship("Reward", back_populates="user", cascade="all, delete-orphan")
    badges = relationship("Badge", back_populates="user", cascade="all, delete-orphan")
    certificate = relationship("Certificate", back_populates="user", uselist=False, cascade="all, delete-orphan")
