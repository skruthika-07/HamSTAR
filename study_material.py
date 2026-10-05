from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .base import Timestamps, new_id


class StudyMaterial(Base, Timestamps):
    __tablename__ = "study_materials"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    file_name: Mapped[str] = mapped_column(String(200))
    file_type: Mapped[str] = mapped_column(String(20))
    file_path: Mapped[str] = mapped_column(String(400))
    file_size: Mapped[int] = mapped_column(default=0)
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    extracted_sections: Mapped[list] = mapped_column(JSON, default=list)
    concepts: Mapped[list] = mapped_column(JSON, default=list)
    # the subfolder it belongs to: its subject or subtopic ("Physics", "Object-Oriented Programming", …); any subject is allowed
    subject: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # the parent folder that subject sits in ("Maths", "Science", "Computer Science", …)
    parent_subject: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # verified bank topic this material maps to, if any
    topic: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # PENDING | PROCESSED | FAILED
    processing_status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User", back_populates="materials")
    questions = relationship("Question", back_populates="material", cascade="all, delete-orphan")
