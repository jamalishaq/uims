import enum

from sqlalchemy import String, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class StaffType(str, enum.Enum):
    ACADEMIC = "academic"       # lecturers, professors
    NON_ACADEMIC = "non_academic"  # admin officers, lab technicians


class StaffRank(str, enum.Enum):
    GRADUATE_ASSISTANT = "graduate_assistant"
    ASSISTANT_LECTURER = "assistant_lecturer"
    LECTURER_II = "lecturer_ii"
    LECTURER_I = "lecturer_i"
    SENIOR_LECTURER = "senior_lecturer"
    ASSOCIATE_PROFESSOR = "associate_professor"
    PROFESSOR = "professor"


class Staff(TimestampMixin, Base):
    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    staff_type: Mapped[StaffType] = mapped_column(Enum(StaffType))
    rank: Mapped[StaffRank | None] = mapped_column(Enum(StaffRank), nullable=True)
    designation: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    user: Mapped["User"] = relationship()
    department: Mapped["Department"] = relationship()
