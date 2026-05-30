from typing import Literal
from pydantic import BaseModel

from app.models.thesis import ThesisStatus


class ThesisRegisterRequest(BaseModel):
    title: str
    supervisor_id: int
    abstract: str | None = None


class ThesisSubmitRequest(BaseModel):
    file_url: str


class ThesisReviewRequest(BaseModel):
    action: Literal["approve", "reject"]
    feedback: str | None = None


class ThesisResponse(BaseModel):
    id: int
    student_id: int
    supervisor_id: int
    title: str | None
    abstract: str | None
    file_url: str | None
    status: ThesisStatus
    supervisor_feedback: str | None

    model_config = {"from_attributes": True}
