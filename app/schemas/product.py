import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class ProductDetailCreate(BaseModel):
    # Changed example to examples for Pydantic v2
    piece_code: Optional[str] = Field(None, examples=["BOX-KUR-001-M"])
    size: Optional[str] = Field(None, examples=["M"])


class ProductDetailResponse(BaseModel):
    # All IDs moved to UUID
    id: uuid.UUID
    product_id: uuid.UUID
    piece_code: Optional[str]
    size: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductCreate(BaseModel):
    # Foreign keys updated to UUID
    tenant_id: uuid.UUID = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])
    category_id: uuid.UUID = Field(..., examples=["71502258-2aac-4108-a84a-f5954db48b0d"])
    set_type_id: Optional[uuid.UUID] = Field(None, examples=["a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d"])
    
    name: str = Field(..., examples=["Kurti A-SET Red"])
    box_code: str = Field(..., examples=["BOX-KUR-001"])
    total_quantity: int = Field(..., examples=[4])
    purchase_price: Optional[Decimal] = Field(None, examples=[800.00])
    selling_price: Optional[Decimal] = Field(None, examples=[1200.00])
    is_active: bool = Field(True)
    
    details: list[ProductDetailCreate] = Field(
        examples=[
            [
                {"piece_code": "BOX-KUR-001-M",   "size": "M"},
                {"piece_code": "BOX-KUR-001-L",   "size": "L"},
                {"piece_code": "BOX-KUR-001-XL",  "size": "XL"},
                {"piece_code": "BOX-KUR-001-XXL", "size": "XXL"},
            ]
        ]
    )


class ProductUpdate(BaseModel):
    # All Foreign keys updated to UUID
    category_id: Optional[uuid.UUID] = None
    set_type_id: Optional[uuid.UUID] = None
    name: Optional[str] = None
    total_quantity: Optional[int] = None
    purchase_price: Optional[Decimal] = None
    selling_price: Optional[Decimal] = None
    is_active: Optional[bool] = None


class ProductResponse(BaseModel):
    # All IDs updated to UUID
    id: uuid.UUID
    tenant_id: uuid.UUID
    category_id: uuid.UUID
    set_type_id: Optional[uuid.UUID]
    
    name: str
    box_code: str
    total_quantity: int
    purchase_price: Optional[Decimal]
    selling_price: Optional[Decimal]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    details: list[ProductDetailResponse] = []

    model_config = ConfigDict(from_attributes=True)


# Lightweight schema used when selecting products for stock entry
class ProductSummary(BaseModel):
    id: uuid.UUID
    name: str
    box_code: str
    total_quantity: int
    details: list[ProductDetailResponse] = []

    model_config = ConfigDict(from_attributes=True)