from __future__ import annotations
from datetime import date
from pydantic import BaseModel


class ExamSlotCreate(BaseModel):
    section_id: int
    date: date
    start_time: str        # "09:00" format
    duration_minutes: int = 120
    venue: str | None = None
    invigilator_id: int | None = None


class ExamSlotOut(BaseModel):
    id: int
    section_id: int
    date: date
    start_time: str
    duration_minutes: int
    venue: str | None = None
    invigilator_id: int | None = None
    model_config = {"from_attributes": True}
