import uuid

from app.schemas.base import CamelModel


class StockUpdate(CamelModel):
    individual_count: int
    bundle_count: int


class StockResponse(CamelModel):
    id: uuid.UUID
    variant_id: uuid.UUID
    individual_count: int
    bundle_count: int
    model_config = {"from_attributes": True}