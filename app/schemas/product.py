import uuid
from typing import Optional, List
from datetime import datetime
from app.models.product import SellType
from app.schemas.base import CamelModel


class ProductVariantCreate(CamelModel):
    color: Optional[str] = None
    pattern: Optional[str] = None
    size: Optional[str] = None
    sku: Optional[str] = None
    image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None


class ProductVariantResponse(CamelModel):
    id: uuid.UUID
    color: Optional[str]
    pattern: Optional[str]
    size: Optional[str]
    sku: Optional[str]
    image_url: Optional[str]
    thumbnail_url: Optional[str]
    is_active: bool
    model_config = {"from_attributes": True}


class ProductCreate(CamelModel):
    tenant_id: uuid.UUID
    category_id: uuid.UUID
    name: str
    model_id: Optional[uuid.UUID] = None
    description: Optional[str] = None
    dp_price: float
    mrp: float
    sell_type: SellType = SellType.both
    is_active: bool = True
    variants: List[ProductVariantCreate] = []


class ProductVariantUpsert(CamelModel):
    """A variant in a nested product update. With `id` → update that variant; without `id`
    → create a new one. Any existing variant not present in the list is removed."""
    id: Optional[uuid.UUID] = None
    color: Optional[str] = None
    pattern: Optional[str] = None
    size: Optional[str] = None
    sku: Optional[str] = None
    image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    is_active: Optional[bool] = None


class ProductUpdate(CamelModel):
    name: Optional[str] = None
    model_id: Optional[uuid.UUID] = None
    description: Optional[str] = None
    dp_price: Optional[float] = None
    mrp: Optional[float] = None
    sell_type: Optional[SellType] = None
    is_active: Optional[bool] = None
    # Omit the field entirely to leave variants untouched. Send a list to sync them:
    # items with `id` are updated, items without `id` are created, and any current
    # variant missing from the list is removed.
    variants: Optional[List[ProductVariantUpsert]] = None


class SetTypeVisibilityUpdate(CamelModel):
    """Hide or show one set type for a single product (catalog display only)."""
    hidden: bool


class ProductResponse(CamelModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    category_id: uuid.UUID
    name: str
    model_id: Optional[uuid.UUID] = None
    model_name: Optional[str] = None
    description: Optional[str]
    dp_price: float
    mrp: float
    sell_type: SellType
    is_active: bool
    variants: List[ProductVariantResponse] = []
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}