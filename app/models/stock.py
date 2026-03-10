import uuid
from sqlalchemy import ForeignKey, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class Stock(BaseModel):
    __tablename__ = "stocks"

    variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_variants.id"), nullable=False, unique=True, index=True
    )
    individual_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bundle_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # bundle_count = number of complete sets available

    variant = relationship("ProductVariant", back_populates="stock")