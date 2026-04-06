import uuid
from typing import Optional, List, Literal
from datetime import datetime
from app.models.order import OrderType, OrderStatus, ReturnType
from app.schemas.base import CamelModel


# ── Create ─────────────────────────────────────────────────────────────────────

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
    assigned_executive: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    items: List[BundleOrderItemCreate]


class IndividualOrderCreate(CamelModel):
    tenant_id: uuid.UUID
    shop_id: uuid.UUID
    distributor_id: Optional[uuid.UUID] = None
    assigned_executive: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    items: List[IndividualOrderItemCreate]


# ── Notes ──────────────────────────────────────────────────────────────────────

class OrderNoteUpdate(CamelModel):
    notes: Optional[str] = None


# ── Assign distributor ─────────────────────────────────────────────────────────

class OrderAssignDistributorInput(CamelModel):
    distributor_id: uuid.UUID
    notes: Optional[str] = None


# ── Discount ───────────────────────────────────────────────────────────────────

class OrderDiscountUpdate(CamelModel):
    discount_percent: Optional[float] = None
    discount_flat: Optional[float] = None
    notes: Optional[str] = None


# ── Dispatch ───────────────────────────────────────────────────────────────────

class OrderDispatchInput(CamelModel):
    delivery_partner: str
    tracking_number: Optional[str] = None
    delivery_notes: Optional[str] = None
    notes: Optional[str] = None


# ── Split ──────────────────────────────────────────────────────────────────────

class SplitItemInput(CamelModel):
    order_item_id: uuid.UUID
    count: int


class SplitOrderInput(CamelModel):
    create_as: Literal["child", "new"]
    items: List[SplitItemInput]
    notes: Optional[str] = None


# ── Return ─────────────────────────────────────────────────────────────────────

class ReturnItemInput(CamelModel):
    order_item_id: uuid.UUID
    return_type: ReturnType
    count: int
    notes: Optional[str] = None


class CreateOrderReturnInput(CamelModel):
    items: List[ReturnItemInput]
    notes: Optional[str] = None


# ── Response ───────────────────────────────────────────────────────────────────

class OrderItemResponse(CamelModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: Optional[str] = None
    product_mrp: Optional[float] = None
    product_dp_price: Optional[float] = None
    variant_id: Optional[uuid.UUID] = None
    variant_sku: Optional[str] = None
    variant_size: Optional[str] = None
    variant_color: Optional[str] = None
    variant_pattern: Optional[str] = None
    variant_thumbnail_url: Optional[str] = None
    set_type_id: Optional[uuid.UUID] = None
    set_type_name: Optional[str] = None
    count: int
    unit_price: float
    total_price: float


class OrderReturnResponse(CamelModel):
    id: uuid.UUID
    order_id: uuid.UUID
    order_item_id: uuid.UUID
    product_id: uuid.UUID
    product_name: Optional[str] = None
    variant_id: Optional[uuid.UUID] = None
    variant_size: Optional[str] = None
    variant_color: Optional[str] = None
    set_type_id: Optional[uuid.UUID] = None
    set_type_name: Optional[str] = None
    return_type: ReturnType
    count: int
    processed_by: uuid.UUID
    processed_by_name: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime


class ShortfallItemResponse(CamelModel):
    order_item_id: uuid.UUID
    product_id: uuid.UUID
    product_name: Optional[str] = None
    variant_id: Optional[uuid.UUID] = None
    variant_size: Optional[str] = None
    variant_color: Optional[str] = None
    set_type_id: Optional[uuid.UUID] = None
    set_type_name: Optional[str] = None
    requested: int
    available: int
    shortfall: int


class EstimateSplitResponse(CamelModel):
    has_shortfall: bool
    shortfall_items: List[ShortfallItemResponse]
    fully_available_items: List[OrderItemResponse]


class ChildOrderSummary(CamelModel):
    id: uuid.UUID
    order_number: str
    status: OrderStatus
    order_type: OrderType
    subtotal: float
    total_amount: float
    notes: Optional[str] = None
    is_child: bool
    items: List[OrderItemResponse] = []
    created_at: datetime
    updated_at: datetime


class OrderResponse(CamelModel):
    id: uuid.UUID
    order_number: str
    tenant_id: uuid.UUID
    tenant_name: Optional[str] = None
    shop_id: uuid.UUID
    shop_name: Optional[str] = None
    shop_contact_person: Optional[str] = None
    shop_contact_number: Optional[str] = None
    shop_phone: Optional[str] = None
    shop_address: Optional[dict] = None
    created_by: uuid.UUID
    created_by_name: Optional[str] = None
    assigned_executive: Optional[uuid.UUID] = None
    assigned_executive_name: Optional[str] = None
    distributor_id: Optional[uuid.UUID] = None
    distributor_name: Optional[str] = None
    distributor_phone: Optional[str] = None
    parent_order_id: Optional[uuid.UUID] = None
    order_type: OrderType
    status: OrderStatus
    discount_percent: float
    discount_flat: float
    subtotal: float
    discount_amount: float
    total_amount: float
    notes: Optional[str] = None
    stock_deducted: bool
    delivery_partner: Optional[str] = None
    tracking_number: Optional[str] = None
    delivery_notes: Optional[str] = None
    items: List[OrderItemResponse] = []
    child_orders: List[ChildOrderSummary] = []
    order_returns: List[OrderReturnResponse] = []
    created_at: datetime
    updated_at: datetime