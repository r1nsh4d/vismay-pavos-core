import uuid
from typing import Optional, List
from datetime import datetime
from app.models.order import OrderType, OrderStatus
from app.schemas.base import CamelModel


# ── Create schemas ─────────────────────────────────────────────────────────────

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
    assigned_executive: Optional[uuid.UUID] = None  # admin can assign to executive
    notes: Optional[str] = None
    items: List[BundleOrderItemCreate]


class IndividualOrderCreate(CamelModel):
    tenant_id: uuid.UUID
    shop_id: uuid.UUID
    distributor_id: Optional[uuid.UUID] = None
    assigned_executive: Optional[uuid.UUID] = None  # admin can assign to executive
    notes: Optional[str] = None
    items: List[IndividualOrderItemCreate]


# ── Update schemas ─────────────────────────────────────────────────────────────

class OrderNoteUpdate(CamelModel):
    notes: Optional[str] = None


class OrderDiscountUpdate(CamelModel):
    discount_percent: float


class OrderAssignDistributorInput(CamelModel):
    distributor_id: uuid.UUID


class OrderDispatchInput(CamelModel):
    delivery_partner: str
    tracking_number: Optional[str] = None
    delivery_notes: Optional[str] = None


# ── Response schemas ───────────────────────────────────────────────────────────

class OrderItemResponse(CamelModel):
    id: uuid.UUID
    product_id: uuid.UUID
    variant_id: Optional[uuid.UUID] = None
    set_type_id: Optional[uuid.UUID] = None
    count: int
    unit_price: float
    total_price: float


class PartialOrderResponse(CamelModel):
    id: uuid.UUID
    order_number: str
    status: OrderStatus
    order_type: OrderType
    subtotal: float
    total_amount: float
    notes: Optional[str] = None
    items: List[OrderItemResponse] = []
    created_at: datetime
    updated_at: datetime


class OrderResponse(CamelModel):
    id: uuid.UUID
    order_number: str
    tenant_id: uuid.UUID
    shop_id: uuid.UUID
    created_by: uuid.UUID
    assigned_executive: Optional[uuid.UUID] = None
    distributor_id: Optional[uuid.UUID] = None
    parent_order_id: Optional[uuid.UUID] = None
    order_type: OrderType
    status: OrderStatus
    discount_percent: float
    subtotal: float
    discount_amount: float
    total_amount: float
    notes: Optional[str] = None
    stock_deducted: bool
    delivery_partner: Optional[str] = None
    tracking_number: Optional[str] = None
    delivery_notes: Optional[str] = None
    items: List[OrderItemResponse] = []
    partial_orders: List[PartialOrderResponse] = []
    created_at: datetime
    updated_at: datetime