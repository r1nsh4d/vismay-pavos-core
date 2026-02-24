from datetime import datetime
from pydantic import BaseModel


class SetTypeDetailCreate(BaseModel):
    value: str


class SetTypeDetailResponse(BaseModel):
    id: int
    set_type_id: int
    value: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SetTypeCreate(BaseModel):
    tenant_id: int
    category_id: int
    name: str
    piece_count: int | None = None
    description: str | None = None
    is_active: bool = True
    details: list[SetTypeDetailCreate] = []


class SetTypeUpdate(BaseModel):
    name: str | None = None
    piece_count: int | None = None
    description: str | None = None
    is_active: bool | None = None


class SetTypeResponse(BaseModel):
    id: int
    tenant_id: int
    category_id: int
    name: str
    piece_count: int | None
    description: str | None
    is_active: bool
    created_at: datetime
    details: list[SetTypeDetailResponse] = []

    model_config = {"from_attributes": True}
