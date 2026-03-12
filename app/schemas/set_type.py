import uuid
from typing import Optional, List
from datetime import datetime

from app.schemas.base import CamelModel


class SetTypeItemCreate(CamelModel):
    size: str
    quantity: int = 1


class SetTypeCreate(CamelModel):
    category_id: uuid.UUID
    name: str
    description: Optional[str] = None
    is_active: bool = True
    items: List[SetTypeItemCreate] = []


class SetTypeUpdate(CamelModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    items: Optional[List[SetTypeItemCreate]] = None  # replaces all items if provided


class SetTypeItemResponse(CamelModel):
    size: str
    quantity: int
    model_config = {"from_attributes": True}


class SetTypeResponse(CamelModel):
    id: uuid.UUID
    category_id: uuid.UUID
    name: str
    description: Optional[str]
    total_pieces: int
    is_active: bool
    items: List[SetTypeItemResponse] = []
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}