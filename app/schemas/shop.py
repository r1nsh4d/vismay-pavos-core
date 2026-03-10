import uuid
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ShopCreate(BaseModel):
    name: str
    place: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    gst_number: Optional[str] = None
    contact_person: Optional[str] = None
    contact_number: Optional[str] = None
    phone: Optional[str] = None
    state: str
    pincode: str
    district_id: uuid.UUID
    is_active: bool = True


class ShopUpdate(BaseModel):
    name: Optional[str] = None
    place: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    gst_number: Optional[str] = None
    contact_person: Optional[str] = None
    contact_number: Optional[str] = None
    phone: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    district_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None


class ShopResponse(BaseModel):
    id: uuid.UUID
    name: str
    place: str
    latitude: Optional[float]
    longitude: Optional[float]
    gst_number: Optional[str]
    contact_person: Optional[str]
    contact_number: Optional[str]
    phone: Optional[str]
    state: str
    pincode: str
    is_active: bool
    district_id: uuid.UUID
    district_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}