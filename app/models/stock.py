import uuid
from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class Stock(BaseModel):
    __tablename__ = "stocks"

    variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_variants.id"), nullable=False, unique=True, index=True
    )
    individual_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    variant = relationship("ProductVariant", back_populates="stock")
    bundle_stocks = relationship("BundleStock", back_populates="stock", cascade="all, delete-orphan")


class BundleStock(BaseModel):
    __tablename__ = "bundle_stocks"

    stock_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stocks.id"), nullable=False, index=True
    )
    set_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("set_types.id"), nullable=False, index=True
    )
    bundle_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    stock = relationship("Stock", back_populates="bundle_stocks")
    set_type = relationship("SetType", backref="bundle_stocks")