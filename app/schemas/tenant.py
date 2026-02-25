from datetime import datetime
from pydantic import BaseModel


class TenantCreate(BaseModel):
    name: str
    code: str
    is_active: bool = True


class TenantUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    is_active: bool | None = None


class TenantResponse(BaseModel):
    id: int
    name: str
    code: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
