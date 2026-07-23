from typing import Any
from enum import Enum
from uuid import UUID
from datetime import datetime, timezone
from dataclasses import dataclass

class IIVCVerificationStatus(str, Enum):
    NOT_APPLICABLE = "Not Applicable"
    PENDING = "Pending"
    VERIFIED = "Verified"
    REJECTED = "Rejected"

class EntryRoute(str, Enum):
    UTME = "UTME"
    DIRECT_ENTRY = "Direct Entry"

class ScreeningStatus(str, Enum):
    PENDING = "Pending"
    SCREENED = "Screened"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    WAITLISTED = "Waitlisted"

@dataclass
class Application:
    application_id: UUID
    first_name: str
    middle_name: str
    last_name: str
    address: str
    phone_number: str
    email: str
    state_of_origin: str
    lga_of_origin: str
    is_indegene: bool
    roles: list[str] = ["Applicant"]
    jamb_registration_number: str
    jamb_scores: dict[str, int]
    jamb_total_score:  int
    jamb_entry_route: EntryRoute
    olevel_grades: dict[str, int]
    aggregate_score: float
    first_choice_confirmed: bool
    program_id: str
    iivc_verification_status: IIVCVerificationStatus = IIVCVerificationStatus.PENDING
    screening_status: ScreeningStatus = ScreeningStatus.PENDING
    # Audit Trail Fields
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None
    # add created_at, updated_at to orm definition

    def edit_application(self, changes: dict[str, Any]) -> None:
        allowed_fields = {"first_name", "middle_name", "last_name", "address", "program_id", "state_of_origin", "lga_of_origin"}
    
        for key, value in changes.items():
            if key in allowed_fields and value is not None:
                setattr(self, key, value)

    def accept_application(self) -> None:
        self.screening_status = ScreeningStatus.ACCEPTED
        self.reviewed_at = datetime.now(timezone.utc)

    def reject_application(self, reason: str) -> None:
        self.screening_status = ScreeningStatus.REJECTED
        self.rejection_reason = reason
        self.reviewed_at = datetime.now(timezone.utc)

    def confrim_application(self) -> None:
        self.screening_status = ScreeningStatus.SCREENED
        self.reviewed_at = datetime.now(timezone.utc)

    def waitlist_application(self) -> None:
        self.screening_status = ScreeningStatus.WAITLISTED
        self.reviewed_at = datetime.now(timezone.utc)

    def verify_iivc(self, is_valid: bool) -> None:
        if is_valid:
            self.iivc_verification_status = IIVCVerificationStatus.VERIFIED
        else:
            self.iivc_verification_status = IIVCVerificationStatus.FAILED
            self.is_indegene = False