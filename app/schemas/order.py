from datetime import datetime
from pydantic import BaseModel
from app.models.order import OrderStatus


class OrderItemCreate(BaseModel):
    product_id: int
    boxes_requested: int


class OrderCreate(BaseModel):
    tenant_id: int
    shop_id: int
    category_id: int
    notes: str | None = None
    items: list[OrderItemCreate]  # all must be same category


class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    boxes_requested: int
    boxes_fulfilled: int
    boxes_pending: int
    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: int
    tenant_id: int
    shop_id: int
    category_id: int
    placed_by: int | None
    parent_order_id: int | None
    status: OrderStatus
    order_ref: str | None
    notes: str | None
    items: list[OrderItemResponse] = []
    submitted_at: datetime | None
    forwarded_at: datetime | None
    approved_at: datetime | None
    estimated_at: datetime | None
    billed_at: datetime | None
    dispatched_at: datetime | None
    delivered_at: datetime | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class OrderStatusUpdateRequest(BaseModel):
    notes: str | None = None