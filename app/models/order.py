import uuid
import enum
from typing import Optional
from sqlalchemy import String, ForeignKey, Boolean, Numeric, Integer, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class OrderType(str, enum.Enum):
    bundle = "bundle"
    individual = "individual"


class OrderStatus(str, enum.Enum):
    placed = "placed"
    approved = "approved"
    rejected = "rejected"
    on_hold = "on_hold"
    estimated = "estimated"
    counting = "counting"
    packing = "packing"
    dispatched = "dispatched"
    delivered = "delivered"
    returned = "returned"


class Order(BaseModel):
    __tablename__ = "orders"

    order_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shops.id"), nullable=False, index=True)
    distributor_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    order_type: Mapped[OrderType] = mapped_column(Enum(OrderType, native_enum=False), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus, native_enum=False), default=OrderStatus.placed, nullable=False)

    discount_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    discount_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stock_deducted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    tenant = relationship("Tenant", backref="orders")
    shop = relationship("Shop", backref="orders")
    distributor = relationship("User", foreign_keys=[distributor_id], backref="distributed_orders")
    creator = relationship("User", foreign_keys=[created_by], backref="created_orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


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