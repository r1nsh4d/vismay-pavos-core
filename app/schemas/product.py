from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class ProductDetailCreate(BaseModel):
    piece_code: str | None = None
    size: str | None = None


class ProductDetailResponse(BaseModel):
    id: int
    product_id: int
    piece_code: str | None
    size: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    tenant_id: int
    category_id: int
    set_type_id: int | None = None
    name: str
    box_code: str
    total_quantity: int
    purchase_price: Decimal | None = None
    selling_price: Decimal | None = None
    is_active: bool = True
    details: list[ProductDetailCreate] = []


class ProductUpdate(BaseModel):
    category_id: int | None = None
    set_type_id: int | None = None
    name: str | None = None
    total_quantity: int | None = None
    purchase_price: Decimal | None = None
    selling_price: Decimal | None = None
    is_active: bool | None = None


class ProductResponse(BaseModel):
    id: int
    tenant_id: int
    category_id: int
    set_type_id: int | None
    name: str
    box_code: str
    total_quantity: int
    purchase_price: Decimal | None
    selling_price: Decimal | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    details: list[ProductDetailResponse] = []

    model_config = {"from_attributes": True}


# Lightweight schema used when selecting products for stock entry
class ProductSummary(BaseModel):
    id: int
    name: str
    box_code: str
    total_quantity: int
    details: list[ProductDetailResponse] = []

    model_config = {"from_attributes": True}