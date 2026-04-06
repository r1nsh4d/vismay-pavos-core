import uuid
import enum
from typing import Optional
from sqlalchemy import String, ForeignKey, Integer, Enum, Text, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class ReturnType(str, enum.Enum):
    bundle = "bundle"       # returned as full bundle → restores bundle stock
    individual = "individual"  # returned as loose piece → restores individual stock


class OrderReturn(BaseModel):
    __tablename__ = "order_returns"

    # which order this return belongs to
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id"), nullable=False, index=True
    )

    # which specific order item was returned
    order_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("order_items.id"), nullable=False, index=True
    )

    # product and variant/set_type for stock restoration reference
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id"), nullable=False
    )
    variant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("product_variants.id"), nullable=True
    )
    set_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("set_types.id"), nullable=True
    )

    # how many units returned and how
    return_type: Mapped[ReturnType] = mapped_column(
        Enum(ReturnType, native_enum=False), nullable=False
    )
    count: Mapped[int] = mapped_column(Integer, nullable=False)

    # who processed this return
    processed_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # relationships
    order = relationship("Order", backref="returns")
    order_item = relationship("OrderItem", backref="returns")
    product = relationship("Product", backref="order_returns")
    variant = relationship("ProductVariant", backref="order_returns")
    set_type = relationship("SetType", backref="order_returns")
    processor = relationship("User", backref="processed_returns")