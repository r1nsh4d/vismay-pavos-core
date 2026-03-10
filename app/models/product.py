import uuid
from typing import Optional
from sqlalchemy import String, ForeignKey, Boolean, Text, Numeric, Integer, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from app.models.base import BaseModel


class SellType(str, enum.Enum):
    individual = "individual"
    bundle = "bundle"
    both = "both"


class Product(BaseModel):
    __tablename__ = "products"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id"), nullable=False, index=True)
    set_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("set_types.id"), nullable=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    dp_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    mrp: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    sell_type: Mapped[SellType] = mapped_column(Enum(SellType), default=SellType.both, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant = relationship("Tenant", backref="products")
    category = relationship("Category", back_populates="products")
    set_type = relationship("SetType", backref="products")
    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")


class ProductVariant(BaseModel):
    __tablename__ = "product_variants"

    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    color: Mapped[Optional[str]] = mapped_column(String(100))
    pattern: Mapped[Optional[str]] = mapped_column(String(100))
    size: Mapped[Optional[str]] = mapped_column(String(20))
    sku: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    product = relationship("Product", back_populates="variants")
    stock = relationship("Stock", back_populates="variant", uselist=False)