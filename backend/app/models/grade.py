from sqlalchemy import String, Float, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class GradeScale(Base):
    """
    Configurable per faculty. faculty_id=None means university-wide default.
    Faculty-specific rows take precedence over the university default.
    """
    __tablename__ = "grade_scales"

    id: Mapped[int] = mapped_column(primary_key=True)
    faculty_id: Mapped[int | None] = mapped_column(ForeignKey("faculties.id"), nullable=True)
    min_score: Mapped[float] = mapped_column(Float)
    max_score: Mapped[float] = mapped_column(Float)
    grade: Mapped[str] = mapped_column(String(2))       # A, B, C, D, E, F
    grade_points: Mapped[float] = mapped_column(Float)  # 5.0, 4.0, 3.0, 2.0, 1.0, 0.0
    passed: Mapped[bool] = mapped_column(Boolean, default=True)
