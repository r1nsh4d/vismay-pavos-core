import uuid
from sqlalchemy import ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class ProductSetTypeVisibility(BaseModel):
    """Per-product visibility of a set type.

    A row with ``is_hidden = True`` means the app should NOT offer this set type for this
    product, even though the product has bundle stock for it. Other products that use the
    same (shared, category-level) set type are unaffected.

    This is a catalog/display flag only — order creation is intentionally NOT blocked by it.
    The frontend reads ``isHidden`` on each entry of a product's ``bundleStockSummary`` and
    hides the hidden ones.
    """
    __tablename__ = "product_set_type_visibility"
    __table_args__ = (
        UniqueConstraint("product_id", "set_type_id", name="uq_product_set_type_visibility"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id"), nullable=False, index=True
    )
    set_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("set_types.id"), nullable=False, index=True
    )
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
