from __future__ import annotations
from pydantic import BaseModel
from app.models.admission import ApplicationStatus


class ApplicationCreate(BaseModel):
    program_id: int
    session_id: int
    first_name: str
    last_name: str
    phone: str
    address: str
    date_of_birth: str  # store as string e.g. "1998-05-14"


class ApplicationOut(BaseModel):
    id: int
    user_id: int
    program_id: int
    session_id: int
    status: ApplicationStatus
    first_name: str
    last_name: str
    phone: str
    address: str
    date_of_birth: str
    rejection_reason: str | None = None
    model_config = {"from_attributes": True}


class DecisionRequest(BaseModel):
    action: str  # "accept" or "reject"
    rejection_reason: str | None = None
