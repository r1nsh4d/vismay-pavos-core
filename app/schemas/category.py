from datetime import datetime
from pydantic import BaseModel


class CategoryCreate(BaseModel):
    tenant_id: int
    name: str
    description: str | None = None
    is_active: bool = True


class CategoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class CategoryResponse(BaseModel):
    id: int
    tenant_id: int
    name: str
    description: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
