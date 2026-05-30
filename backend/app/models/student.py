import enum

from sqlalchemy import String, Integer, Float, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class StudentStatus(str, enum.Enum):
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    SUSPENDED = "suspended"
    WITHDRAWN = "withdrawn"
    GRADUATED = "graduated"


class Student(TimestampMixin, Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    matric_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id"))
    level: Mapped[int] = mapped_column(Integer)  # 100, 200, 300, 400, 500
    status: Mapped[StudentStatus] = mapped_column(Enum(StudentStatus), default=StudentStatus.ACTIVE)
    cgpa: Mapped[float] = mapped_column(Float, default=0.0)
    total_credits_passed: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship()
    program: Mapped["Program"] = relationship()
    enrollments: Mapped[list["CourseEnrollment"]] = relationship(back_populates="student")
