from __future__ import annotations
from pydantic import BaseModel
from app.models.course import CourseType


class PrerequisiteOut(BaseModel):
    id: int
    prerequisite_id: int
    model_config = {"from_attributes": True}


class CourseCreate(BaseModel):
    code: str
    title: str
    credit_hours: int
    course_type: CourseType
    department_id: int
    description: str | None = None


class CourseOut(BaseModel):
    id: int
    code: str
    title: str
    credit_hours: int
    course_type: CourseType
    department_id: int
    description: str | None = None
    prerequisites: list[PrerequisiteOut] = []
    model_config = {"from_attributes": True}


class PrerequisiteCreate(BaseModel):
    prerequisite_id: int


class SectionCreate(BaseModel):
    course_id: int
    semester_id: int
    lecturer_id: int
    max_enrollment: int = 50
    venue: str | None = None
    schedule: str | None = None


class SectionOut(BaseModel):
    id: int
    course_id: int
    semester_id: int
    lecturer_id: int
    max_enrollment: int
    venue: str | None = None
    schedule: str | None = None
    model_config = {"from_attributes": True}
