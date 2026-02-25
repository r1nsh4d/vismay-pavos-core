from datetime import datetime
from pydantic import BaseModel


class StockCreate(BaseModel):
    tenant_id: int
    product_id: int
    boxes_total: int
    batch_ref: str | None = None


class StockResponse(BaseModel):
    id: int
    tenant_id: int
    product_id: int
    added_by: int | None
    batch_ref: str | None
    boxes_total: int
    boxes_available: int
    boxes_reserved: int
    boxes_billed: int
    boxes_dispatched: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class StockSummaryResponse(BaseModel):
    """Lightweight — shown to executive when placing order"""
    product_id: int
    product_name: str
    boxes_available: int