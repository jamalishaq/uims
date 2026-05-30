import enum

from sqlalchemy import String, Integer, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class DegreeType(str, enum.Enum):
    BSC = "bsc"
    MSC = "msc"
    PHD = "phd"
    PGDE = "pgde"


class Faculty(TimestampMixin, Base):
    __tablename__ = "faculties"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    dean_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    departments: Mapped[list["Department"]] = relationship(back_populates="faculty")


class Department(TimestampMixin, Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(20), unique=True)
    faculty_id: Mapped[int] = mapped_column(ForeignKey("faculties.id"))
    hod_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    faculty: Mapped[Faculty] = relationship(back_populates="departments")
    programs: Mapped[list["Program"]] = relationship(back_populates="department")


class Program(TimestampMixin, Base):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(20), unique=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))
    degree_type: Mapped[DegreeType] = mapped_column(Enum(DegreeType))
    duration_years: Mapped[int] = mapped_column(Integer)
    total_credits_required: Mapped[int] = mapped_column(Integer)
    core_credits_required: Mapped[int] = mapped_column(Integer)
    elective_credits_required: Mapped[int] = mapped_column(Integer)

    department: Mapped[Department] = relationship(back_populates="programs")
