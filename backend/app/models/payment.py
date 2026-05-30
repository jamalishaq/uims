import enum

from sqlalchemy import String, Float, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class FeeType(str, enum.Enum):
    TUITION = "tuition"
    ACCEPTANCE = "acceptance"
    APPLICATION = "application"
    ACCOMMODATION = "accommodation"
    LIBRARY = "library"
    DEPARTMENT = "department"
    EXAM = "exam"
    LATE_REGISTRATION = "late_registration"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    PAID = "paid"


class FeeSchedule(TimestampMixin, Base):
    """Defines what is owed per fee type, per semester, optionally per program."""
    __tablename__ = "fee_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(ForeignKey("semesters.id"))
    program_id: Mapped[int | None] = mapped_column(ForeignKey("programs.id"), nullable=True)
    fee_type: Mapped[FeeType] = mapped_column(Enum(FeeType))
    amount: Mapped[float] = mapped_column(Float)


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    semester_id: Mapped[int | None] = mapped_column(ForeignKey("semesters.id"), nullable=True)
    fee_type: Mapped[FeeType] = mapped_column(Enum(FeeType))
    amount_due: Mapped[float] = mapped_column(Float)
    amount_paid: Mapped[float] = mapped_column(Float, default=0.0)
    balance: Mapped[float] = mapped_column(Float)
    paystack_reference: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
