import uuid
import enum
from typing import Optional
from sqlalchemy import String, ForeignKey, Boolean, Text, Numeric, Integer, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class OrderStatus(str, enum.Enum):
    estimated = "estimated"
    pending = "pending"
    confirmed = "confirmed"
    counting = "counting"
    packing = "packing"
    partial = "partial"
    dispatched = "dispatched"
    delivered = "delivered"
    cancelled = "cancelled"


class OrderItemType(str, enum.Enum):
    individual = "individual"
    bundle = "bundle"


class Order(BaseModel):
    __tablename__ = "orders"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shops.id"), nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), default=OrderStatus.estimated, nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant = relationship("Tenant", backref="orders")
    shop = relationship("Shop", backref="orders")
    created_by_user = relationship("User", backref="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(BaseModel):
    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    variant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product_variants.id"), nullable=False)
    item_type: Mapped[OrderItemType] = mapped_column(Enum(OrderItemType), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    total_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    order = relationship("Order", back_populates="items")
    variant = relationship("ProductVariant", backref="order_items")