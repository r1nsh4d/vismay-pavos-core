import uuid
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from app.models.order import OrderStatus, OrderItemType


class OrderItemCreate(BaseModel):
    variant_id: uuid.UUID
    item_type: OrderItemType
    quantity: int
    unit_price: float


class OrderItemResponse(BaseModel):
    id: uuid.UUID
    variant_id: uuid.UUID
    item_type: OrderItemType
    quantity: int
    unit_price: float
    total_price: float
    model_config = {"from_attributes": True}


class OrderCreate(BaseModel):
    tenant_id: uuid.UUID
    shop_id: uuid.UUID
    notes: Optional[str] = None
    items: List[OrderItemCreate]


class OrderUpdate(BaseModel):
    notes: Optional[str] = None
    status: Optional[OrderStatus] = None


class OrderResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    shop_id: uuid.UUID
    created_by: uuid.UUID
    status: OrderStatus
    notes: Optional[str]
    total_amount: float
    is_active: bool
    items: List[OrderItemResponse] = []
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}