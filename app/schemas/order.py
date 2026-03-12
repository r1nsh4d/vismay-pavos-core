import uuid
from typing import Optional, List
from datetime import datetime
from app.models.order import OrderType, OrderStatus
from app.schemas.base import CamelModel


class OrderItemCreate(CamelModel):
    product_id: uuid.UUID
    variant_id: Optional[uuid.UUID] = None    # individual only
    set_type_id: Optional[uuid.UUID] = None   # bundle only
    count: int


class OrderCreate(CamelModel):
    tenant_id: uuid.UUID
    shop_id: uuid.UUID
    distributor_id: Optional[uuid.UUID] = None
    order_type: OrderType
    notes: Optional[str] = None
    items: List[OrderItemCreate]


class OrderStatusUpdate(CamelModel):
    status: OrderStatus


class OrderDiscountUpdate(CamelModel):
    discount_percent: float


class OrderItemResponse(CamelModel):
    id: uuid.UUID
    product_id: uuid.UUID
    variant_id: Optional[uuid.UUID]
    set_type_id: Optional[uuid.UUID]
    count: int
    unit_price: float
    total_price: float


class OrderResponse(CamelModel):
    id: uuid.UUID
    order_number: str
    tenant_id: uuid.UUID
    shop_id: uuid.UUID
    distributor_id: Optional[uuid.UUID]
    created_by: uuid.UUID
    order_type: OrderType
    status: OrderStatus
    discount_percent: float
    subtotal: float
    discount_amount: float
    total_amount: float
    notes: Optional[str]
    stock_deducted: bool
    items: List[OrderItemResponse] = []
    created_at: datetime
    updated_at: datetime

class BundleOrderItemCreate(CamelModel):
    product_id: uuid.UUID
    set_type_id: uuid.UUID
    count: int


class IndividualOrderItemCreate(CamelModel):
    product_id: uuid.UUID
    variant_id: uuid.UUID
    count: int


class BundleOrderCreate(CamelModel):
    tenant_id: uuid.UUID
    shop_id: uuid.UUID
    distributor_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    items: List[BundleOrderItemCreate]


class IndividualOrderCreate(CamelModel):
    tenant_id: uuid.UUID
    shop_id: uuid.UUID
    distributor_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    items: List[IndividualOrderItemCreate]