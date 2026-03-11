from pydantic import EmailStr
from typing import Optional, List, Any
import uuid
from datetime import datetime

from app.schemas.base import CamelModel


# ── Role-specific profile schemas (for documentation + optional validation) ────

class AddressProfile(CamelModel):
    place: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "place": "MG Road",
                "state": "Kerala",
                "pincode": "682001",
                "latitude": 9.9312,
                "longitude": 76.2673,
            }
        }
    }


class DistributorProfile(CamelModel):
    """profile_data shape for distributor role"""
    company_name: Optional[str] = None
    gst_number: Optional[str] = None
    contact_person: Optional[str] = None
    contact_number: Optional[str] = None
    alternate_phone: Optional[str] = None
    taluk_id: Optional[uuid.UUID] = None
    address: Optional[AddressProfile] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "company_name": "Vismay Distributors Pvt Ltd",
                "gst_number": "32ABCDE1234F1Z5",
                "contact_person": "Rahul Menon",
                "contact_number": "9876543210",
                "alternate_phone": "9876500000",
                "taluk_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                "address": {
                    "place": "MG Road",
                    "state": "Kerala",
                    "pincode": "682001",
                    "latitude": 9.9312,
                    "longitude": 76.2673,
                },
            }
        }
    }


class ExecutiveProfile(CamelModel):
    """profile_data shape for admin / executive roles"""
    employee_id: Optional[str] = None
    department: Optional[str] = None
    alternate_phone: Optional[str] = None
    address: Optional[AddressProfile] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "employee_id": "EMP-001",
                "department": "Sales",
                "alternate_phone": "9876543210",
                "address": {
                    "place": "Kakkanad",
                    "state": "Kerala",
                    "pincode": "682030",
                },
            }
        }
    }


# ── Association responses ──────────────────────────────────────────────────────

class UserTenantResponse(CamelModel):
    tenant_id: uuid.UUID
    tenant_name: str
    tenant_code: str
    is_active: bool


class UserDistrictResponse(CamelModel):
    district_id: uuid.UUID
    district_name: str
    state_name: Optional[str] = None
    state_code: Optional[str] = None
    is_active: bool


# ── User CRUD ──────────────────────────────────────────────────────────────────

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
    profile_data: Optional[dict] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "rahul_menon",
                "firstName": "Rahul",
                "lastName": "Menon",
                "email": "rahul@example.com",
                "phone": "9876543210",
                "password": "Secret@123",
                "roleId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "tenantIds": [],
                "districtIds": [],
                "profileData": {
                    "company_name": "Vismay Distributors Pvt Ltd",
                    "gst_number": "32ABCDE1234F1Z5",
                    "contact_person": "Rahul Menon",
                    "contact_number": "9876543210",
                    "taluk_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                    "address": {
                        "place": "MG Road",
                        "state": "Kerala",
                        "pincode": "682001",
                    },
                },
            }
        }
    }


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
    user_tenants: List[dict] = []
    user_districts: List[dict] = []
    profile_data: Optional[dict] = None