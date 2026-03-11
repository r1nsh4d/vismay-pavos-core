import uuid
from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel


class ShopAddress(BaseModel):
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
                "longitude": 76.2673
            }
        }
    }


class ShopCreate(BaseModel):
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
                "name": "Vismay Textiles",
                "gst_number": "32ABCDE1234F1Z5",
                "contact_person": "Rahul Menon",
                "contact_number": "9876543210",
                "phone": "04842345678",
                "address": {
                    "place": "MG Road",
                    "state": "Kerala",
                    "pincode": "682001",
                    "latitude": 9.9312,
                    "longitude": 76.2673
                },
                "district_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "taluk_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                "is_active": True
            }
        }
    }


class ShopUpdate(BaseModel):
    name: Optional[str] = None
    gst_number: Optional[str] = None
    contact_person: Optional[str] = None
    contact_number: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[ShopAddress] = None
    district_id: Optional[uuid.UUID] = None
    taluk_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None


class ShopResponse(BaseModel):
    id: uuid.UUID
    name: str
    gst_number: Optional[str]
    contact_person: Optional[str]
    contact_number: Optional[str]
    phone: Optional[str]
    address: Optional[Any]
    is_active: bool
    district_id: uuid.UUID
    district_name: Optional[str] = None
    taluk_id: Optional[uuid.UUID] = None
    taluk_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}