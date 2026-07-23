from uuid import UUID
from pydantic import BaseModel, EmailStr

from backend.src.domain.models import Role

# --- Request Schemas ---

class AccountCreateRequest(BaseModel):
    email: EmailStr
    password: str
    active_role: Role
    roles: list[Role]
    owner_id: UUID
    is_active: bool = True

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class SwitchRoleRequest(BaseModel):
    user_id: str
    target_role: Role
    current_refresh_token: str | None = None

class LogoutRequest(BaseModel):
    refresh_token: str

class LogoutAllRequest(BaseModel):
    user_id: str


# --- Response Schemas ---

class AccountResponse(BaseModel):
    user_id: UUID
    email: EmailStr
    active_role: Role
    roles: list[Role]
    owner_id: UUID
    is_active: bool

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"