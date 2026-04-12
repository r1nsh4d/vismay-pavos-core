import uuid
from typing import Optional, List, Literal
from datetime import datetime
from app.models.order import OrderType, OrderStatus, ReturnType, PriceType
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
    price_type: PriceType = PriceType.mrp
    items: List[BundleOrderItemCreate]


class IndividualOrderCreate(CamelModel):
    tenant_id: uuid.UUID
    shop_id: uuid.UUID
    distributor_id: Optional[uuid.UUID] = None
    assigned_executive: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    price_type: PriceType = PriceType.mrp
    items: List[IndividualOrderItemCreate]


# ── Updates ────────────────────────────────────────────────────────────────────

class OrderNoteUpdate(CamelModel):
    notes: Optional[str] = None


class OrderAssignDistributorInput(CamelModel):
    distributor_id: uuid.UUID
    notes: Optional[str] = None


class OrderDiscountUpdate(CamelModel):
    discount_percent: Optional[float] = None
    discount_flat: Optional[float] = None
    notes: Optional[str] = None


class OrderDispatchInput(CamelModel):
    delivery_partner: str
    tracking_number: Optional[str] = None
    tracking_link: Optional[str] = None
    delivery_notes: Optional[str] = None
    notes: Optional[str] = None


class UpdateDeliveredAtInput(CamelModel):
    delivered_at: datetime
    notes: Optional[str] = None


class UpdateOrderItemInput(CamelModel):
    count: int


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


# ── Responses ──────────────────────────────────────────────────────────────────

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
    returned_count: int = 0
    remaining_count: int = 0
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


class ChildOrderSummary(CamelModel):
    id: uuid.UUID
    order_number: str
    status: OrderStatus
    order_type: OrderType
    price_type: PriceType
    subtotal: float
    discount_percent: float
    discount_flat: float
    discount_amount: float
    total_amount: float
    notes: Optional[str] = None
    stock_deducted: bool
    is_child: bool
    item_count: int = 0
    items: List[OrderItemResponse] = []
    created_at: datetime
    updated_at: datetime


class StatusTimestamps(CamelModel):
    placed_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    assigned_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    estimated_at: Optional[datetime] = None
    billed_at: Optional[datetime] = None
    packing_at: Optional[datetime] = None
    dispatched_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    returned_at: Optional[datetime] = None


class OrderListResponse(CamelModel):
    id: uuid.UUID
    order_number: str
    tenant_id: uuid.UUID
    tenant_name: Optional[str] = None
    shop_id: uuid.UUID
    shop_name: Optional[str] = None
    shop_phone: Optional[str] = None
    created_by: uuid.UUID
    created_by_name: Optional[str] = None
    assigned_executive: Optional[uuid.UUID] = None
    assigned_executive_name: Optional[str] = None
    distributor_id: Optional[uuid.UUID] = None
    distributor_name: Optional[str] = None
    parent_order_id: Optional[uuid.UUID] = None
    order_type: OrderType
    status: OrderStatus
    price_type: PriceType
    discount_percent: float
    discount_flat: float
    subtotal: float
    discount_amount: float
    total_amount: float
    notes: Optional[str] = None
    stock_deducted: bool
    item_count: int = 0
    placed_at: Optional[datetime] = None
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
    price_type: PriceType
    discount_percent: float
    discount_flat: float
    subtotal: float
    discount_amount: float
    total_amount: float
    notes: Optional[str] = None
    stock_deducted: bool
    delivery_partner: Optional[str] = None
    tracking_number: Optional[str] = None
    tracking_link: Optional[str] = None
    delivery_notes: Optional[str] = None
    status_timestamps: Optional[StatusTimestamps] = None
    items: List[OrderItemResponse] = []
    child_orders: List[ChildOrderSummary] = []
    order_returns: List[OrderReturnResponse] = []
    created_at: datetime
    updated_at: datetime