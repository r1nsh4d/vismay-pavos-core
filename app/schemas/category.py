import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional


class CategoryCreate(BaseModel):
    # Changed from int to uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: Optional[str] = None
    is_active: bool = True


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class CategoryResponse(BaseModel):
    # All IDs updated to UUID
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime

    # Modern Pydantic v2 configuration
    model_config = ConfigDict(from_attributes=True)