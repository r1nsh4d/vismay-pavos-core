

import uuid
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, TIMESTAMP, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.category import Category
    from app.models.product import Product

class SetType(Base):
    __tablename__ = "set_types"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)

    # 1. Primary Key: UUID with auto-generation
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    
    # 2. Foreign Keys: Matching the parent UUID types
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"), 
        nullable=False
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"), 
        nullable=False
    )
    
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    piece_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))
    created_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now())

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="set_types")
    category: Mapped["Category"] = relationship("Category", back_populates="set_types")
    details: Mapped[list["SetTypeDetail"]] = relationship("SetTypeDetail", back_populates="set_type", cascade="all, delete")
    products: Mapped[list["Product"]] = relationship("Product", back_populates="set_type")


class SetTypeDetail(Base):
    __tablename__ = "set_type_details"
    __table_args__ = (UniqueConstraint("set_type_id", "value"),)

    # Primary Key: UUID
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    
    # Foreign Key: Must match SetType.id
    set_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("set_types.id", ondelete="CASCADE"), 
        nullable=False
    )
    
    value: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now())

    # Relationships
    set_type: Mapped["SetType"] = relationship("SetType", back_populates="details")