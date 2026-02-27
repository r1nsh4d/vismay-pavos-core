from __future__ import annotations

import uuid
import enum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, TIMESTAMP, Enum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.shop import Shop
    from app.models.category import Category
    from app.models.product import Product
    from app.models.user import User
    from app.models.stock import Stock


class OrderStatus(str, enum.Enum):
    PLACED = "PLACED"
    SUBMITTED = "SUBMITTED"
    FORWARDED = "FORWARDED"
    APPROVED = "APPROVED"
    HOLD = "HOLD"
    CANCELLED = "CANCELLED"
    ESTIMATED = "ESTIMATED"
    BILLED = "BILLED"
    COUNTING = "COUNTING"
    PACKING = "PACKING"
    DISPATCHED = "DISPATCHED"
    DELIVERED = "DELIVERED"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # All Foreign Keys updated to UUID
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    shop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    placed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    parent_order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)

    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.PLACED, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_ref: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)

    # Timestamps
    submitted_at: Mapped[any] = mapped_column(TIMESTAMP, nullable=True)
    forwarded_at: Mapped[any] = mapped_column(TIMESTAMP, nullable=True)
    approved_at: Mapped[any] = mapped_column(TIMESTAMP, nullable=True)
    estimated_at: Mapped[any] = mapped_column(TIMESTAMP, nullable=True)
    billed_at: Mapped[any] = mapped_column(TIMESTAMP, nullable=True)
    dispatched_at: Mapped[any] = mapped_column(TIMESTAMP, nullable=True)
    delivered_at: Mapped[any] = mapped_column(TIMESTAMP, nullable=True)
    created_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    shop: Mapped["Shop"] = relationship("Shop")
    category: Mapped["Category"] = relationship("Category")
    placed_by_user: Mapped["User"] = relationship("User")
    items: Mapped[list["OrderItem"]] = relationship("OrderItem", back_populates="order", cascade="all, delete")
    child_orders: Mapped[list["Order"]] = relationship("Order", foreign_keys=[parent_order_id])


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)

    boxes_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    boxes_fulfilled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    boxes_pending: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now())

    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped["Product"] = relationship("Product")
    allocations: Mapped[list["OrderItemAllocation"]] = relationship(
        "OrderItemAllocation", back_populates="order_item", cascade="all, delete"
    )


class OrderItemAllocation(Base):
    """Tracks which stock batch is locked for which order item — FIFO"""
    __tablename__ = "order_item_allocations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False)
    stock_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    boxes_allocated: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now())

    order_item: Mapped["OrderItem"] = relationship("OrderItem", back_populates="allocations")
    stock: Mapped["Stock"] = relationship("Stock", back_populates="allocations")