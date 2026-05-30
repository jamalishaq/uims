from datetime import date

from sqlalchemy import String, Integer, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class ExamSlot(TimestampMixin, Base):
    __tablename__ = "exam_slots"
    __table_args__ = (UniqueConstraint("section_id", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("course_sections.id"))
    date: Mapped[date] = mapped_column(Date)
    start_time: Mapped[str] = mapped_column(String(5))   # e.g. "09:00"
    duration_minutes: Mapped[int] = mapped_column(Integer, default=120)
    venue: Mapped[str | None] = mapped_column(String(200), nullable=True)
    invigilator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    section: Mapped["CourseSection"] = relationship()
    invigilator: Mapped["User"] = relationship()
