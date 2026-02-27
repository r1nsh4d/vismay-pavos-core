import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ShopCreate(BaseModel):
    # Changed from int to uuid.UUID
    district_id: uuid.UUID
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
    # All IDs updated to UUID
    id: uuid.UUID
    district_id: uuid.UUID
    created_by: uuid.UUID | None
    
    name: str
    address: str | None
    location: str | None
    contact: str | None
    contact_person: str | None
    gst_number: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Modern Pydantic v2 configuration
    model_config = ConfigDict(from_attributes=True)