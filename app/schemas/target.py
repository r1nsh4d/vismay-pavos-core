import uuid
from typing import Optional
from app.models.target import TargetType
from app.schemas.base import CamelModel


class TargetCreate(CamelModel):
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    year: int
    month: int
    target_type: TargetType
    target_value: float
    notes: Optional[str] = None


class TargetResponse(CamelModel):
    id: uuid.UUID
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    year: int
    month: int
    target_type: TargetType
    target_value: float
    notes: Optional[str] = None