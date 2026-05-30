from pydantic import BaseModel

from app.models.hostel import RoomType


class HostelOut(BaseModel):
    id: int
    name: str
    gender: str
    model_config = {"from_attributes": True}


class RoomOut(BaseModel):
    id: int
    hostel_id: int
    room_number: str
    room_type: RoomType
    capacity: int
    is_available: bool
    hostel_name: str | None = None
    model_config = {"from_attributes": True}


class ApplyRequest(BaseModel):
    semester_id: int
    preferred_room_type: RoomType | None = None


class AllocationOut(BaseModel):
    id: int
    student_id: int
    room_id: int
    semester_id: int
    is_active: bool
    model_config = {"from_attributes": True}


class AllocateRequest(BaseModel):
    student_id: int
    room_id: int
    semester_id: int
