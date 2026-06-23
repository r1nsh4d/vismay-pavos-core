import uuid
import enum
from typing import Optional
from sqlalchemy import String, ForeignKey, Boolean, Numeric, Integer, Enum, Text, Index, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship, backref
from app.models.base import BaseModel


class OrderType(str, enum.Enum):
    bundle = "bundle"
    individual = "individual"


class OrderStatus(str, enum.Enum):
    placed = "placed"
    verified = "verified"
    assigned = "assigned"
    approved = "approved"
    on_hold = "on_hold"
    rejected = "rejected"
    cancelled = "cancelled"
    estimated = "estimated"
    billed = "billed"
    packing = "packing"
    dispatched = "dispatched"
    delivered = "delivered"
    partially_returned = "partially_returned"
    returned = "returned"


class ReturnType(str, enum.Enum):
    bundle = "bundle"
    individual = "individual"


class PriceType(str, enum.Enum):
    mrp = "mrp"
    dp = "dp"


CANCELLABLE_STATUSES = {
    OrderStatus.placed,
    OrderStatus.verified,
    OrderStatus.assigned,
    OrderStatus.approved,
    OrderStatus.on_hold,
    OrderStatus.estimated,
}

STOCK_RESTORE_STATUSES = {
    OrderStatus.placed,
    OrderStatus.verified,
    OrderStatus.assigned,
    OrderStatus.approved,
    OrderStatus.on_hold,
    OrderStatus.estimated,
}


class Order(BaseModel):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_tenant_status", "tenant_id", "status"),
        Index("ix_orders_executive_status", "assigned_executive", "status"),
        Index("ix_orders_distributor_status", "distributor_id", "status"),
        Index("ix_orders_shop_id", "shop_id"),
        Index("ix_orders_created_at", "created_at"),
        Index("ix_orders_parent_order_id", "parent_order_id"),
    )

    order_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shops.id"), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_executive: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    distributor_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    parent_order_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("orders.id"), nullable=True)

    order_type: Mapped[OrderType] = mapped_column(Enum(OrderType, native_enum=False), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False), default=OrderStatus.placed, nullable=False
    )
    price_type: Mapped[PriceType] = mapped_column(
        Enum(PriceType, native_enum=False), default=PriceType.mrp, nullable=False
    )

    discount_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    discount_flat: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    discount_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stock_deducted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Delivery info
    delivery_partner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tracking_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tracking_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    delivery_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dispatched_box_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bill_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    # Status timestamps
    placed_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
    estimated_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
    billed_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
    packing_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
    dispatched_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
    returned_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant = relationship("Tenant", backref="orders")
    shop = relationship("Shop", backref="orders")
    creator = relationship("User", foreign_keys=[created_by], backref="created_orders")
    executive = relationship("User", foreign_keys=[assigned_executive], backref="executive_orders")
    distributor = relationship("User", foreign_keys=[distributor_id], backref="distributed_orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    order_returns = relationship("OrderReturn", back_populates="order", cascade="all, delete-orphan")
    child_orders = relationship(
        "Order",
        foreign_keys="[Order.parent_order_id]",
        backref=backref("parent_order", remote_side="Order.id"),
    )


class OrderItem(BaseModel):
    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    variant_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("product_variants.id"), nullable=True)
    set_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("set_types.id"), nullable=True)

    count: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    total_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product", backref="order_items")
    variant = relationship("ProductVariant", backref="order_items")
    set_type = relationship("SetType", backref="order_items")
    item_returns = relationship("OrderReturn", back_populates="order_item")


class OrderReturn(BaseModel):
    __tablename__ = "order_returns"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    order_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("order_items.id"), nullable=False, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    variant_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("product_variants.id"), nullable=True)
    set_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("set_types.id"), nullable=True)

    return_type: Mapped[ReturnType] = mapped_column(Enum(ReturnType, native_enum=False), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    processed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    order = relationship("Order", back_populates="order_returns")
    order_item = relationship("OrderItem", back_populates="item_returns")
    product = relationship("Product", backref="order_returns")
    variant = relationship("ProductVariant", backref="order_returns")
    set_type = relationship("SetType", backref="order_returns")
    processor = relationship("User", backref="processed_returns")