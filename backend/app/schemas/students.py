from pydantic import BaseModel
from app.models.student import StudentStatus


class StudentListItem(BaseModel):
    id: int
    user_id: int
    matric_number: str
    program_id: int
    level: int
    status: StudentStatus
    cgpa: float
    model_config = {"from_attributes": True}


class StudentOut(BaseModel):
    id: int
    user_id: int
    matric_number: str
    program_id: int
    level: int
    status: StudentStatus
    cgpa: float
    total_credits_passed: int
    username: str
    email: str
    model_config = {"from_attributes": True}


class StatusUpdateRequest(BaseModel):
    status: StudentStatus
