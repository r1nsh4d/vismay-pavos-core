from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text, TIMESTAMP, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.category import Category
    from app.models.product import Product

class SetType(Base):
    __tablename__ = "set_types"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    piece_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now())

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="set_types")
    category: Mapped["Category"] = relationship("Category", back_populates="set_types")
    details: Mapped[list["SetTypeDetail"]] = relationship("SetTypeDetail", back_populates="set_type", cascade="all, delete")
    products: Mapped[list["Product"]] = relationship("Product", back_populates="set_type")


class SetTypeDetail(Base):
    __tablename__ = "set_type_details"
    __table_args__ = (UniqueConstraint("set_type_id", "value"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    set_type_id: Mapped[int] = mapped_column(ForeignKey("set_types.id", ondelete="CASCADE"), nullable=False)
    value: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now())

    # Relationships
    set_type: Mapped["SetType"] = relationship("SetType", back_populates="details")
