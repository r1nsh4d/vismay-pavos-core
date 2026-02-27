from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, TIMESTAMP, func, text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.product import Product
    from app.models.user import User
    from app.models.order import OrderItemAllocation


class Stock(Base):
    __tablename__ = "stocks"

    # Primary Key: UUID with auto-generation
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )

    # Foreign Keys: Updated to match UUID parents
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"), 
        nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"), 
        nullable=False
    )
    added_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )

    batch_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    boxes_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    boxes_available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    boxes_reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    boxes_billed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    boxes_dispatched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))
    created_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    product: Mapped["Product"] = relationship("Product")
    added_by_user: Mapped["User"] = relationship("User")
    allocations: Mapped[list["OrderItemAllocation"]] = relationship("OrderItemAllocation", back_populates="stock")