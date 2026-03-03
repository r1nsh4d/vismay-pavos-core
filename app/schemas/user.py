# ─── Role-specific profiles ───────────────────────────────────────────────────
import datetime
import uuid
from typing import Optional

from app.schemas.base import CamelModel


class AdminProfileCreate(CamelModel):
    department_name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None


class AdminProfileResponse(CamelModel):
    id: uuid.UUID
    department_name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None


class DistributorProfileCreate(CamelModel):
    company_name: Optional[str] = None
    gst: Optional[str] = None
    address: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    taluk: Optional[str] = None


class DistributorProfileResponse(CamelModel):
    id: uuid.UUID
    company_name: Optional[str] = None
    gst: Optional[str] = None
    address: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    taluk: Optional[str] = None


class ExecutiveProfileCreate(CamelModel):
    designation: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    pincode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    reporting_admin_id: Optional[uuid.UUID] = None


class ExecutiveProfileResponse(CamelModel):
    id: uuid.UUID
    designation: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    pincode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    reporting_admin_id: Optional[uuid.UUID] = None


# ─── User ─────────────────────────────────────────────────────────────────────

class UserTenantResponse(CamelModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    is_active: bool
    name: str
    code: str


class UserDistrictResponse(CamelModel):
    id: uuid.UUID
    district_id: uuid.UUID
    is_active: bool
    name: str
    state: str


class UserCreate(CamelModel):
    username: str
    first_name: str
    last_name: Optional[str] = None
    email: EmailStr
    phone: Optional[str] = None
    password: str
    role_id: Optional[uuid.UUID] = None
    tenant_ids: list[uuid.UUID] = []
    district_ids: list[uuid.UUID] = []

    # Role-specific profile — only one should be provided
    admin_profile: Optional[AdminProfileCreate] = None
    distributor_profile: Optional[DistributorProfileCreate] = None
    executive_profile: Optional[ExecutiveProfileCreate] = None


class UserUpdate(CamelModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None

    admin_profile: Optional[AdminProfileCreate] = None
    distributor_profile: Optional[DistributorProfileCreate] = None
    executive_profile: Optional[ExecutiveProfileCreate] = None


class UserResponse(CamelModel):
    id: uuid.UUID
    username: str
    first_name: str
    last_name: Optional[str] = None
    email: str
    phone: Optional[str] = None
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    role_id: Optional[uuid.UUID] = None
    role: Optional[str] = None
    permissions: list[str] = []

    user_tenants: list[UserTenantResponse] = []
    user_districts: list[UserDistrictResponse] = []

    # Only the relevant one will be populated
    admin_profile: Optional[AdminProfileResponse] = None
    distributor_profile: Optional[DistributorProfileResponse] = None
    executive_profile: Optional[ExecutiveProfileResponse] = None