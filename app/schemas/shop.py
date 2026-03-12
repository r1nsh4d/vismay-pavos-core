import uuid
from typing import Optional, Any
from datetime import datetime

from app.schemas.base import CamelModel


class ShopAddress(CamelModel):
    place: Optional[str] = None
    state_id: Optional[uuid.UUID] = None
    state_name: Optional[str] = None
    state_code: Optional[str] = None
    pincode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "place": "MG Road",
                "state_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "state_name": "Kerala",
                "state_code": "KL",
                "pincode": "682001",
                "latitude": 9.9312,
                "longitude": 76.2673,
            }
        }
    }


class ShopCreate(CamelModel):
    name: str
    gst_number: Optional[str] = None
    contact_person: Optional[str] = None
    contact_number: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[ShopAddress] = None
    district_id: uuid.UUID
    taluk_id: Optional[uuid.UUID] = None
    is_active: bool = True

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Seemas Aluva",
                "gst_number": "32ABCDE1234F1Z5",
                "contact_person": "Rahul Menon",
                "contact_number": "9876543210",
                "phone": "04842345678",
                "address": {
                    "place": "MG Road",
                    "state_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "state_name": "Kerala",
                    "state_code": "KL",
                    "pincode": "682001",
                    "latitude": 9.9312,
                    "longitude": 76.2673,
                },
                "district_id": "667aa3ae-9c86-4058-ba14-9fc511209a13",
                "taluk_id": "084479ae-0319-40dd-bf9e-1351b31bf45e",
                "is_active": True,
            }
        }
    }


class ShopUpdate(CamelModel):
    name: Optional[str] = None
    gst_number: Optional[str] = None
    contact_person: Optional[str] = None
    contact_number: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[ShopAddress] = None
    district_id: Optional[uuid.UUID] = None
    taluk_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None


class ShopResponse(CamelModel):
    id: uuid.UUID
    name: str
    gst_number: Optional[str] = None
    contact_person: Optional[str] = None
    contact_number: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[Any] = None
    is_active: bool
    district_id: uuid.UUID
    district_name: Optional[str] = None
    state_id: Optional[str] = None
    state_name: Optional[str] = None
    taluk_id: Optional[uuid.UUID] = None
    taluk_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}