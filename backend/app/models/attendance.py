import enum
from datetime import date

from sqlalchemy import Date, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class AttendanceStatus(str, enum.Enum):
    PRESENT = "present"
    ABSENT = "absent"
    EXCUSED = "excused"


class AttendanceRecord(TimestampMixin, Base):
    __tablename__ = "attendance_records"
    __table_args__ = (UniqueConstraint("section_id", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("course_sections.id"))
    date: Mapped[date] = mapped_column(Date)

    entries: Mapped[list["AttendanceEntry"]] = relationship(back_populates="record")


class AttendanceEntry(Base):
    __tablename__ = "attendance_entries"
    __table_args__ = (UniqueConstraint("record_id", "student_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("attendance_records.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    status: Mapped[AttendanceStatus] = mapped_column(Enum(AttendanceStatus), default=AttendanceStatus.PRESENT)

    record: Mapped[AttendanceRecord] = relationship(back_populates="entries")
