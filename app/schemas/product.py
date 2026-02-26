from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class ProductDetailCreate(BaseModel):
    piece_code: str | None = Field(None, example="BOX-KUR-001-M")
    size: str | None = Field(None, example="M")


class ProductDetailResponse(BaseModel):
    id: int
    product_id: int
    piece_code: str | None
    size: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    tenant_id: int = Field(..., example=1)
    category_id: int = Field(..., example=2)
    set_type_id: int | None = Field(None, example=1)
    name: str = Field(..., example="Kurti A-SET Red")
    box_code: str = Field(..., example="BOX-KUR-001")
    total_quantity: int = Field(..., example=4)
    purchase_price: Decimal | None = Field(None, example=800.00)
    selling_price: Decimal | None = Field(None, example=1200.00)
    is_active: bool = Field(True)
    details: list[ProductDetailCreate] = Field(
        example=[
            {"piece_code": "BOX-KUR-001-M",   "size": "M"},
            {"piece_code": "BOX-KUR-001-L",   "size": "L"},
            {"piece_code": "BOX-KUR-001-XL",  "size": "XL"},
            {"piece_code": "BOX-KUR-001-XXL", "size": "XXL"},
        ]
    )


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