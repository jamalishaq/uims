from pydantic import BaseModel, EmailStr

from app.models.staff import StaffType, StaffRank


class StaffCreateRequest(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    department_id: int | None = None
    staff_type: StaffType
    rank: StaffRank | None = None
    designation: str | None = None
    phone: str | None = None


class StaffUserResponse(BaseModel):
    id: int
    email: str
    username: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


class StaffResponse(BaseModel):
    id: int
    user_id: int
    department_id: int | None
    staff_type: StaffType
    rank: StaffRank | None
    designation: str | None
    phone: str | None
    user: StaffUserResponse

    model_config = {"from_attributes": True}
