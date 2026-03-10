import uuid
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel


class SetTypeItemCreate(BaseModel):
    size: str
    quantity: int = 1


class SetTypeCreate(BaseModel):
    category_id: uuid.UUID
    name: str
    description: Optional[str] = None
    is_active: bool = True
    items: List[SetTypeItemCreate] = []


class SetTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    items: Optional[List[SetTypeItemCreate]] = None  # replaces all items if provided


class SetTypeItemResponse(BaseModel):
    size: str
    quantity: int
    model_config = {"from_attributes": True}


class SetTypeResponse(BaseModel):
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