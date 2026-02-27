import uuid
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, String, TIMESTAMP, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.role import Role
    from app.models.user import UserTenant
    from app.models.category import Category
    from app.models.set_type import SetType
    from app.models.product import Product

class Tenant(Base):
    __tablename__ = "tenants"

    # Changed from int to UUID with automatic generation
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))
    
    created_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    # Note: Ensure Role, UserTenant, Category, etc., all use UUID for their tenant_id foreign keys
    roles: Mapped[list["Role"]] = relationship("Role", back_populates="tenant", cascade="all, delete")
    user_tenants: Mapped[list["UserTenant"]] = relationship("UserTenant", back_populates="tenant", cascade="all, delete")
    categories: Mapped[list["Category"]] = relationship("Category", back_populates="tenant", cascade="all, delete")
    set_types: Mapped[list["SetType"]] = relationship("SetType", back_populates="tenant", cascade="all, delete")
    products: Mapped[list["Product"]] = relationship("Product", back_populates="tenant", cascade="all, delete")