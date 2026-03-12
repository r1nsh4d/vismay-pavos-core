import uuid
from typing import Optional
from datetime import datetime

from app.schemas.base import CamelModel


class StateCreate(CamelModel):
    name: str
    code: str
    is_active: bool = True


class StateUpdate(CamelModel):
    name: Optional[str] = None
    code: Optional[str] = None
    is_active: Optional[bool] = None


class StateResponse(CamelModel):
    id: uuid.UUID
    name: str
    code: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}