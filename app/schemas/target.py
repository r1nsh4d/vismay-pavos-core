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
    category_id: Optional[uuid.UUID] = None  # required when target_type = category_quantity
    notes: Optional[str] = None

    def validate_category(self):
        if self.target_type == TargetType.category_quantity and not self.category_id:
            raise ValueError("category_id is required for category_quantity target type")


class TargetResponse(CamelModel):
    id: uuid.UUID
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    year: int
    month: int
    target_type: TargetType
    target_value: float
    category_id: Optional[uuid.UUID] = None
    category_name: Optional[str] = None
    notes: Optional[str] = None