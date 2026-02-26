<<<<<<< Updated upstream
from datetime import datetime
from pydantic import BaseModel, Field


class StockCreate(BaseModel):
    tenant_id: int = Field(..., example=1)
    product_id: int = Field(..., example=1)
    boxes_total: int = Field(..., example=10)
    batch_ref: str | None = Field(None, example="BATCH-2026-001")


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
=======
from datetime import datetime
from pydantic import BaseModel, Field


class StockCreate(BaseModel):
    tenant_id: int = Field(..., example=1)
    product_id: int = Field(..., example=1)
    boxes_total: int = Field(..., example=10)
    batch_ref: str | None = Field(None, example="BATCH-2026-001")


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
>>>>>>> Stashed changes
    boxes_available: int