import uuid
from pydantic import BaseModel


class StockUpdate(BaseModel):
    individual_count: int
    bundle_count: int


class StockResponse(BaseModel):
    id: uuid.UUID
    variant_id: uuid.UUID
    individual_count: int
    bundle_count: int
    model_config = {"from_attributes": True}