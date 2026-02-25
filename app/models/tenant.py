from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, Boolean, String, TIMESTAMP, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.role import Role
    from app.models.user import User
    from app.models.category import Category
    from app.models.set_type import SetType
    from app.models.product import Product

class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    roles: Mapped[list["Role"]] = relationship("Role", back_populates="tenant", cascade="all, delete")
    users: Mapped[list["User"]] = relationship("User", back_populates="tenant", cascade="all, delete")
    categories: Mapped[list["Category"]] = relationship("Category", back_populates="tenant", cascade="all, delete")
    set_types: Mapped[list["SetType"]] = relationship("SetType", back_populates="tenant", cascade="all, delete")
    products: Mapped[list["Product"]] = relationship("Product", back_populates="tenant", cascade="all, delete")
