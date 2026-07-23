from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr
from src.domain.models import EntryRoute, IIVCVerificationStatus, ScreeningStatus

# --- Nested Input Schemas for Creation ---

class ApplicantDetails(BaseModel):
    first_name: str
    middle_name: str | None = None
    last_name: str
    address: str
    phone_number: str
    email: EmailStr
    state_of_origin: str
    lga_of_origin: str


class JambDetails(BaseModel):
    jamb_registration_number: str
    jamb_scores: dict[str, int]
    jamb_total_score: int
    jamb_entry_route: EntryRoute


# --- Main Request Models ---

class ApplicationCreateRequest(BaseModel):
    applicant_details: ApplicantDetails
    jamb_details: JambDetails
    olevel_grades: dict[str, int]
    is_indegene: bool
    program_id: str


class ApplicationEditRequest(BaseModel):
    """Partial update model allowing optional edits to applicant data."""
    first_name: str | None = None
    middle_name: str | None = None
    last_name: str | None = None
    address: str | None = None
    phone_number: str | None = None
    email: EmailStr | None = None
    state_of_origin: str | None = None
    lga_of_origin: str | None = None
    is_indegene: bool | None = None
    olevel_grades: dict[str, int] | None = None
    program_id: str | None = None


class ApplicationRejectRequest(BaseModel):
    """Optional schema if rejecting requires capturing a reason."""
    rejection_reason: str


# --- Response Models ---

class ApplicationResponse(BaseModel):
    """Full representation of an Application returned by the API."""
    model_config = ConfigDict(from_attributes=True)

    application_id: UUID
    first_name: str
    middle_name: str
    last_name: str
    address: str
    phone_number: str
    email: EmailStr
    state_of_origin: str
    lga_of_origin: str
    is_indegene: bool
    roles: list[str]
    jamb_registration_number: str
    jamb_scores: dict[str, int]
    jamb_total_score: int
    jamb_entry_route: EntryRoute
    olevel_grades: dict[str, int]
    aggregate_score: float
    first_choice_confirmed: bool
    program_id: str
    iivc_verification_status: IIVCVerificationStatus
    screening_status: ScreeningStatus
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None
