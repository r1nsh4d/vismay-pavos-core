from pydantic import BaseModel, EmailStr, ConfigDict, Field
from typing import Optional, List
import uuid
from datetime import datetime

from app.schemas.base import CamelModel


# User associations
class UserTenantResponse(CamelModel):
    tenant_id: uuid.UUID
    tenant_name: str
    tenant_code: str
    is_active: bool


class UserDistrictResponse(CamelModel):
    district_id: uuid.UUID
    district_name: str
    state: str
    is_active: bool


# User
class UserCreate(CamelModel):
    username: str
    first_name: str
    last_name: Optional[str] = None
    email: EmailStr
    phone: Optional[str] = None
    password: str
    role_id: Optional[uuid.UUID] = None
    tenant_ids: List[uuid.UUID] = []
    district_ids: List[uuid.UUID] = []
    profile_data: Optional[dict] = None  # e.g., {"company_name": "ABC", "gst": "123"}


class UserUpdate(CamelModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None
    profile_data: Optional[dict] = None


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
    role_name: Optional[str] = None
    permissions: List[str] = []
    user_tenants: List[UserTenantResponse] = []
    user_districts: List[UserDistrictResponse] = []
    profile_data: Optional[dict] = None