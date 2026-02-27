import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class TenantCreate(BaseModel):
    name: str
    code: str
    is_active: bool = True


class TenantUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    is_active: bool | None = None


class TenantResponse(BaseModel):
    # Changed from int to uuid.UUID
    id: uuid.UUID
    name: str
    code: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Modern Pydantic v2 configuration
    model_config = ConfigDict(from_attributes=True)