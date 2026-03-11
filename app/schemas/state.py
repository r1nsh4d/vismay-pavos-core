import uuid
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class StateCreate(BaseModel):
    name: str
    code: str
    is_active: bool = True


class StateUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    is_active: Optional[bool] = None


class StateResponse(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}