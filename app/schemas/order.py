import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional
from app.models.order import OrderStatus


class OrderItemCreate(BaseModel):
    # Changed from int to uuid.UUID
    product_id: uuid.UUID
    boxes_requested: int


class OrderCreate(BaseModel):
    # All relational IDs moved to UUID
    tenant_id: uuid.UUID
    shop_id: uuid.UUID
    category_id: uuid.UUID
    notes: Optional[str] = None
    items: list[OrderItemCreate]  # all must be same category


class OrderItemResponse(BaseModel):
    # Primary and Foreign keys changed to UUID
    id: uuid.UUID
    product_id: uuid.UUID
    boxes_requested: int
    boxes_fulfilled: int
    boxes_pending: int
    
    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    # Comprehensive UUID update for the entire order tree
    id: uuid.UUID
    tenant_id: uuid.UUID
    shop_id: uuid.UUID
    category_id: uuid.UUID
    placed_by: Optional[uuid.UUID]
    parent_order_id: Optional[uuid.UUID]
    
    status: OrderStatus
    order_ref: Optional[str]
    notes: Optional[str]
    items: list[OrderItemResponse] = []
    
    # Timestamps
    submitted_at: Optional[datetime]
    forwarded_at: Optional[datetime]
    approved_at: Optional[datetime]
    estimated_at: Optional[datetime]
    billed_at: Optional[datetime]
    dispatched_at: Optional[datetime]
    delivered_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class OrderStatusUpdateRequest(BaseModel):
    notes: Optional[str] = None