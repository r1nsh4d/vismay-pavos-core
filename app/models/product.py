from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, Numeric, String, TIMESTAMP, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, pk_type


if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.category import Category
    from app.models.set_type import SetType


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(pk_type(), primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    set_type_id: Mapped[int | None] = mapped_column(ForeignKey("set_types.id", ondelete="SET NULL"), nullable=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    box_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    total_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    purchase_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    selling_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))
    created_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="products")
    category: Mapped["Category"] = relationship("Category", back_populates="products")
    set_type: Mapped["SetType"] = relationship("SetType", back_populates="products")
    details: Mapped[list["ProductDetail"]] = relationship(
        "ProductDetail", back_populates="product", cascade="all, delete"
    )


class ProductDetail(Base):
    __tablename__ = "product_details"

    id: Mapped[int] = mapped_column(pk_type(), primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    piece_code: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now())

    product: Mapped["Product"] = relationship("Product", back_populates="details")