from __future__ import annotations
from datetime import date
from pydantic import BaseModel
from app.models.attendance import AttendanceStatus


class AttendanceEntryInput(BaseModel):
    student_id: int
    status: AttendanceStatus = AttendanceStatus.PRESENT


class MarkAttendanceRequest(BaseModel):
    date: date
    entries: list[AttendanceEntryInput]


class AttendanceSummaryItem(BaseModel):
    student_id: int
    matric_number: str
    total_classes: int
    attended: int
    percentage: float
    below_threshold: bool  # True if percentage < 75
