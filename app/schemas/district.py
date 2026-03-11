import uuid
from typing import Optional
from datetime import datetime
from app.schemas.base import CamelModel


class DistrictCreate(CamelModel):
    name: str
    state_id: uuid.UUID
    is_active: bool = True


class DistrictUpdate(CamelModel):
    name: Optional[str] = None
    state_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None


class DistrictResponse(CamelModel):
    id: uuid.UUID
    name: str
    state_id: uuid.UUID
    state_name: Optional[str] = None
    state_code: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}