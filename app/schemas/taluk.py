import uuid
from typing import Optional
from datetime import datetime
from app.schemas.base import CamelModel


class TalukCreate(CamelModel):
    name: str
    district_id: uuid.UUID
    is_active: bool = True


class TalukUpdate(CamelModel):
    name: Optional[str] = None
    district_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None


class TalukResponse(CamelModel):
    id: uuid.UUID
    name: str
    district_id: uuid.UUID
    district_name: Optional[str] = None
    state_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}