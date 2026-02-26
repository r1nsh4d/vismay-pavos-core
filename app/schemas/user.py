from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator, model_validator
from sqlalchemy import inspect as sa_inspect


class TenantInfo(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}


class DistrictInfo(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}


class TenantInUser(BaseModel):
    id: int
    tenant_id: int
    is_active: bool
    tenant: TenantInfo  # ← added
    model_config = {"from_attributes": True}


class DistrictInUser(BaseModel):
    id: int
    district_id: int
    is_active: bool
    district: DistrictInfo  # ← added
    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    role_id: int | None = None
    username: str
    first_name: str
    last_name: str | None = None
    email: EmailStr
    phone: str | None = None
    password: str
    is_active: bool = True
    is_verified: bool = False
    tenant_ids: list[int] = []    # empty for SUPER_ADMIN
    district_ids: list[int] = []  # empty for SUPER_ADMIN


class UserUpdate(BaseModel):
    role_id: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    username: str | None = None
    is_active: bool | None = None
    is_verified: bool | None = None


class RoleInUser(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}


class PermissionInfo(BaseModel):
    id: int
    name: str
    code: str
    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: int
    role_id: int | None
    role: str | None = None
    permissions: list[str] = []
    username: str
    first_name: str
    last_name: str | None
    email: str
    phone: str | None
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    user_tenants: list[TenantInUser] = []
    user_districts: list[DistrictInUser] = []
    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def extract_role_and_permissions(cls, v):
        if hasattr(v, "role") and v.role is not None:
            role_obj = v.role
            # extract role name
            v.__dict__["role"] = role_obj.name
            # extract permissions
            if hasattr(role_obj, "role_permissions"):
                v.__dict__["permissions"] = [
                    rp.permission.code for rp in role_obj.role_permissions
                ]
        return v


class AssignTenantsRequest(BaseModel):
    tenant_ids: list[int]


class AssignDistrictsRequest(BaseModel):
    district_ids: list[int]


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str