import enum

from sqlalchemy import String, Text, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class ThesisStatus(str, enum.Enum):
    TOPIC_SUBMITTED = "topic_submitted"
    TOPIC_APPROVED = "topic_approved"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class Thesis(TimestampMixin, Base):
    __tablename__ = "theses"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), unique=True)
    supervisor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[ThesisStatus] = mapped_column(Enum(ThesisStatus), default=ThesisStatus.TOPIC_SUBMITTED)
    supervisor_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
