import enum
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy import Enum, String, JSON, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin

class IIVCVerificationStatus(str, enum.Enum):
    NOT_APPLICABLE = "Not Applicable"
    PENDING = "Pending"
    VERIFIED = "Verified"
    REJECTED = "Rejected"

class EntryRoute(str, enum.Enum):
    UTME = "UTME"
    DIRECT_ENTRY = "Direct Entry"

class ScreeningStatus(str, enum.Enum):
    PENDING = "Pending"
    SCREENED = "Screened"
    ADMITTED = "Admitted"
    REJECTED = "Rejected"
    WAITLISTED = "Waitlisted"

class ApplicationORM(Base, TimestampMixin):
    __tablename__ = "applications"

    application_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    program_id: Mapped[UUID] = mapped_column(ForeignKey("programs.program_id"), index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    middle_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(100))
    phone_number: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(100))
    state_of_origin: Mapped[str] = mapped_column(String(20))
    lga_of_origin: Mapped[str] = mapped_column(String(20))
    roles: Mapped[list[str]] = mapped_column(JSON)
    jamb_registration_number: Mapped[str] = mapped_column(String(20))
    jamb_scores: Mapped[dict[str, int]] = mapped_column(JSON)
    jamb_total_scores: Mapped[int] = mapped_column()
    jamb_entry_route: Mapped[EntryRoute] = mapped_column(Enum(EntryRoute))
    olevel_gradess: Mapped[dict[str, int]] = mapped_column(JSON)
    aggregate_score: Mapped[float] = mapped_column()
    first_choice_confirmed: Mapped[bool] = mapped_column()
    is_indegene: Mapped[bool] = mapped_column()
    iivc_verification_status: Mapped[IIVCVerificationStatus] = mapped_column(Enum(IIVCVerificationStatus))
    screening_status: Mapped[ScreeningStatus] = mapped_column(Enum(ScreeningStatus))
    # Audit Trail Fields
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(String(200))
    
    