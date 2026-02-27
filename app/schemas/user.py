import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, model_validator, ConfigDict
from typing import Optional

class TenantInfo(BaseModel):
    id: uuid.UUID
    name: str
    code:str
    model_config = ConfigDict(from_attributes=True)


class DistrictInfo(BaseModel):
    id: uuid.UUID
    name: str
    model_config = ConfigDict(from_attributes=True)


class TenantInUser(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    is_active: bool
    tenant: TenantInfo
    model_config = ConfigDict(from_attributes=True)


class DistrictInUser(BaseModel):
    id: uuid.UUID
    district_id: uuid.UUID
    is_active: bool
    district: DistrictInfo
    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    role_id: Optional[uuid.UUID] = None
    username: str
    first_name: str
    last_name: Optional[str] = None
    email: EmailStr
    phone: Optional[str] = None
    password: str
    is_active: bool = True
    is_verified: bool = False
    tenant_ids: list[uuid.UUID] = []    # Changed to list of UUIDs
    district_ids: list[uuid.UUID] = []  # Changed to list of UUIDs


class UserUpdate(BaseModel):
    role_id: Optional[uuid.UUID] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    username: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None


class RoleInUser(BaseModel):
    id: uuid.UUID
    name: str
    model_config = ConfigDict(from_attributes=True)


class PermissionInfo(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    id: uuid.UUID
    role_id: Optional[uuid.UUID]
    role: Optional[str] = None
    permissions: list[str] = []
    username: str
    first_name: str
    last_name: Optional[str]
    email: str
    phone: Optional[str]
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    user_tenants: list[TenantInUser] = []
    user_districts: list[DistrictInUser] = []
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def extract_role_and_permissions(cls, v):
        # We use __dict__ or getattr because 'v' is often a SQLAlchemy model instance
        role_obj = getattr(v, "role", None)
        if role_obj:
            # Manually inject string values into the validation dict
            if hasattr(v, "__dict__"):
                v.__dict__["role"] = role_obj.name
                if hasattr(role_obj, "role_permissions"):
                    v.__dict__["permissions"] = [
                        rp.permission.code for rp in role_obj.role_permissions
                    ]
        return v


class AssignTenantsRequest(BaseModel):
    tenant_ids: list[uuid.UUID]


class AssignDistrictsRequest(BaseModel):
    district_ids: list[uuid.UUID]


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str