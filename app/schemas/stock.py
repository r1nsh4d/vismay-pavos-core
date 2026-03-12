import uuid
from pydantic import model_validator
from typing import Optional, List

from app.schemas.base import CamelModel


class IndividualStockAdd(CamelModel):
    variant_id: uuid.UUID
    count: int


class BundleStockAdd(CamelModel):
    product_id: uuid.UUID
    set_type_id: uuid.UUID
    bundle_count: int


class BundleStockResponse(CamelModel):
    set_type_id: uuid.UUID
    set_type_name: Optional[str] = None
    bundle_count: int
    model_config = {"from_attributes": True}


class StockResponse(CamelModel):
    id: uuid.UUID
    variant_id: uuid.UUID
    individual_count: int
    bundle_stocks: List[BundleStockResponse] = []
    model_config = {"from_attributes": True}


class VariantStockResponse(CamelModel):
    variant_id: uuid.UUID
    size: Optional[str]
    color: Optional[str]
    sku: Optional[str]
    individual_count: int
    bundle_count: int  # count specific to the queried set_type


class SetTypeStockResponse(CamelModel):
    product_id: uuid.UUID
    set_type_id: uuid.UUID
    set_type_name: str
    variants: List[VariantStockResponse]