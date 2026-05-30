from __future__ import annotations
from datetime import date
from pydantic import BaseModel
from app.models.academic import DegreeType
from app.models.calendar import SemesterName


class FacultyCreate(BaseModel):
    name: str
    code: str

class FacultyOut(BaseModel):
    id: int
    name: str
    code: str
    dean_id: int | None = None
    model_config = {"from_attributes": True}

class DepartmentCreate(BaseModel):
    name: str
    code: str
    faculty_id: int

class DepartmentOut(BaseModel):
    id: int
    name: str
    code: str
    faculty_id: int
    model_config = {"from_attributes": True}

class ProgramCreate(BaseModel):
    name: str
    code: str
    department_id: int
    degree_type: DegreeType
    duration_years: int
    total_credits_required: int
    core_credits_required: int
    elective_credits_required: int

class ProgramOut(BaseModel):
    id: int
    name: str
    code: str
    department_id: int
    degree_type: DegreeType
    duration_years: int
    total_credits_required: int
    core_credits_required: int
    elective_credits_required: int
    model_config = {"from_attributes": True}

class SessionCreate(BaseModel):
    name: str
    start_date: date
    end_date: date
    is_current: bool = False

class SessionOut(BaseModel):
    id: int
    name: str
    start_date: date
    end_date: date
    is_current: bool
    model_config = {"from_attributes": True}

class SemesterCreate(BaseModel):
    name: SemesterName
    start_date: date
    end_date: date
    registration_start: date
    registration_end: date
    is_current: bool = False

class SemesterOut(BaseModel):
    id: int
    session_id: int
    name: SemesterName
    start_date: date
    end_date: date
    registration_start: date
    registration_end: date
    is_current: bool
    model_config = {"from_attributes": True}
