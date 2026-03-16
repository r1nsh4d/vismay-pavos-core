import uuid
from typing import Optional
from datetime import datetime
from app.schemas.base import CamelModel


class ModelCreate(CamelModel):
    category_id: uuid.UUID
    name: str
    description: Optional[str] = None
    is_active: bool = True


class ModelUpdate(CamelModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class ModelResponse(CamelModel):
    id: uuid.UUID
    category_id: uuid.UUID
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}