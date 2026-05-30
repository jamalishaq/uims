import enum

from sqlalchemy import String, Text, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class ApplicationStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    SCREENING = "screening"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ENROLLED = "enrolled"


class Application(TimestampMixin, Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id"))
    session_id: Mapped[int] = mapped_column(ForeignKey("academic_sessions.id"))
    status: Mapped[ApplicationStatus] = mapped_column(Enum(ApplicationStatus), default=ApplicationStatus.SUBMITTED)

    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20))
    address: Mapped[str] = mapped_column(Text)
    date_of_birth: Mapped[str] = mapped_column(String(20))

    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
