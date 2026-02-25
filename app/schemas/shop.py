from datetime import datetime
from pydantic import BaseModel


class ShopCreate(BaseModel):
    district_id: int
    name: str
    address: str | None = None
    location: str | None = None
    contact: str | None = None
    contact_person: str | None = None
    gst_number: str | None = None
    is_active: bool = True


class ShopUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    location: str | None = None
    contact: str | None = None
    contact_person: str | None = None
    gst_number: str | None = None
    is_active: bool | None = None


class ShopResponse(BaseModel):
    id: int
    district_id: int
    created_by: int | None
    name: str
    address: str | None
    location: str | None
    contact: str | None
    contact_person: str | None
    gst_number: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}