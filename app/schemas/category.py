import uuid
from typing import Optional
from datetime import datetime

from app.schemas.base import CamelModel


class CategoryCreate(CamelModel):
    tenant_id: uuid.UUID
    name: str
    description: Optional[str] = None
    is_active: bool = True


class CategoryUpdate(CamelModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class CategoryResponse(CamelModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}