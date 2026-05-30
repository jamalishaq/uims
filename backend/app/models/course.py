import enum

from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, Enum, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class CourseType(str, enum.Enum):
    CORE = "core"
    ELECTIVE = "elective"
    GENERAL = "general"


class EnrollmentStatus(str, enum.Enum):
    REGISTERED = "registered"
    DROPPED = "dropped"
    COMPLETED = "completed"
    CARRYOVER = "carryover"


class Course(TimestampMixin, Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    credit_hours: Mapped[int] = mapped_column(Integer)
    course_type: Mapped[CourseType] = mapped_column(Enum(CourseType))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    prerequisites: Mapped[list["CoursePrerequisite"]] = relationship(
        foreign_keys="CoursePrerequisite.course_id", back_populates="course"
    )
    sections: Mapped[list["CourseSection"]] = relationship(back_populates="course")


class CoursePrerequisite(Base):
    __tablename__ = "course_prerequisites"
    __table_args__ = (UniqueConstraint("course_id", "prerequisite_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    prerequisite_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))

    course: Mapped[Course] = relationship(foreign_keys=[course_id], back_populates="prerequisites")
    prerequisite: Mapped[Course] = relationship(foreign_keys=[prerequisite_id])


class CourseSection(TimestampMixin, Base):
    __tablename__ = "course_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    semester_id: Mapped[int] = mapped_column(ForeignKey("semesters.id"))
    lecturer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    max_enrollment: Mapped[int] = mapped_column(Integer, default=50)
    venue: Mapped[str | None] = mapped_column(String(100), nullable=True)
    schedule: Mapped[str | None] = mapped_column(String(200), nullable=True)  # e.g. "Mon/Wed 10:00-11:30"

    course: Mapped[Course] = relationship(back_populates="sections")
    enrollments: Mapped[list["CourseEnrollment"]] = relationship(back_populates="section")


class CourseEnrollment(TimestampMixin, Base):
    __tablename__ = "course_enrollments"
    __table_args__ = (UniqueConstraint("student_id", "section_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    section_id: Mapped[int] = mapped_column(ForeignKey("course_sections.id"))
    status: Mapped[EnrollmentStatus] = mapped_column(Enum(EnrollmentStatus), default=EnrollmentStatus.REGISTERED)
    ca_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    exam_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    grade: Mapped[str | None] = mapped_column(String(2), nullable=True)
    grade_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    student: Mapped["Student"] = relationship(back_populates="enrollments")
    section: Mapped[CourseSection] = relationship(back_populates="enrollments")
