import enum
from datetime import date

from sqlalchemy import String, Boolean, Date, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class SemesterName(str, enum.Enum):
    FIRST = "first"
    SECOND = "second"
    SUMMER = "summer"


class AcademicSession(TimestampMixin, Base):
    __tablename__ = "academic_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(20), unique=True)  # e.g. "2024/2025"
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)

    semesters: Mapped[list["Semester"]] = relationship(back_populates="session")


class Semester(TimestampMixin, Base):
    __tablename__ = "semesters"
    __table_args__ = (UniqueConstraint("session_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("academic_sessions.id"))
    name: Mapped[SemesterName] = mapped_column(Enum(SemesterName))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    registration_start: Mapped[date] = mapped_column(Date)
    registration_end: Mapped[date] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)

    session: Mapped[AcademicSession] = relationship(back_populates="semesters")
