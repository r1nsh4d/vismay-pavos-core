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


class ProductVariantResponse(CamelModel):
    id: uuid.UUID
    color: Optional[str]
    pattern: Optional[str]
    size: Optional[str]
    sku: Optional[str]
    is_active: bool
    model_config = {"from_attributes": True}


class ProductCreate(CamelModel):
    tenant_id: uuid.UUID
    category_id: uuid.UUID
    set_type_id: Optional[uuid.UUID] = None
    name: str
    model: Optional[str] = None
    description: Optional[str] = None
    dp_price: float
    mrp: float
    sell_type: SellType = SellType.both
    is_active: bool = True
    variants: List[ProductVariantCreate] = []


class ProductUpdate(CamelModel):
    name: Optional[str] = None
    model: Optional[str] = None
    description: Optional[str] = None
    dp_price: Optional[float] = None
    mrp: Optional[float] = None
    sell_type: Optional[SellType] = None
    set_type_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None


class ProductResponse(CamelModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    category_id: uuid.UUID
    set_type_id: Optional[uuid.UUID]
    name: str
    model: Optional[str]
    description: Optional[str]
    dp_price: float
    mrp: float
    sell_type: SellType
    is_active: bool
    variants: List[ProductVariantResponse] = []
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}