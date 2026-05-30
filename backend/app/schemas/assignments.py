from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel


class AssignmentCreate(BaseModel):
    section_id: int
    title: str
    description: str | None = None
    due_date: datetime
    max_score: float = 100.0


class AssignmentOut(BaseModel):
    id: int
    section_id: int
    title: str
    description: str | None = None
    due_date: datetime
    max_score: float
    model_config = {"from_attributes": True}


class SubmitAssignmentRequest(BaseModel):
    file_url: str


class GradeSubmissionRequest(BaseModel):
    score: float
    feedback: str | None = None


class SubmissionOut(BaseModel):
    id: int
    assignment_id: int
    student_id: int
    file_url: str | None = None
    score: float | None = None
    feedback: str | None = None
    is_late: bool
    model_config = {"from_attributes": True}
