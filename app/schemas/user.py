from datetime import datetime
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    tenant_id: int | None = None      # None only for SUPER_ADMIN
    district_id: int | None = None
    role_id: int | None = None
    username: str
    first_name: str
    last_name: str | None = None
    email: EmailStr
    phone: str | None = None
    password: str
    is_active: bool = True
    is_verified: bool = False


class UserUpdate(BaseModel):
    tenant_id: int | None = None
    district_id: int | None = None
    role_id: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    username: str | None = None
    is_active: bool | None = None
    is_verified: bool | None = None


class UserResponse(BaseModel):
    id: int
    tenant_id: int | None
    district_id: int | None
    role_id: int | None
    username: str
    first_name: str
    last_name: str | None
    email: str
    phone: str | None
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str