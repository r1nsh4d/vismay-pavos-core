import uuid
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class StockCreate(BaseModel):
    # Changed from int to uuid.UUID
    tenant_id: uuid.UUID = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])
    product_id: uuid.UUID = Field(..., examples=["71502258-2aac-4108-a84a-f5954db48b0d"])
    boxes_total: int = Field(..., example=10)
    batch_ref: str | None = Field(None, example="BATCH-2026-001")


class StockResponse(BaseModel):
    # Primary key and all Foreign keys moved to UUID
    id: uuid.UUID
    tenant_id: uuid.UUID
    product_id: uuid.UUID
    added_by: uuid.UUID | None
    
    batch_ref: str | None
    boxes_total: int
    boxes_available: int
    boxes_reserved: int
    boxes_billed: int
    boxes_dispatched: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    # Updated to modern Pydantic v2 ConfigDict
    model_config = ConfigDict(from_attributes=True)


class StockSummaryResponse(BaseModel):
    """Lightweight — shown to executive when placing order"""
    product_id: uuid.UUID
    product_name: str
    boxes_available: int
    
    model_config = ConfigDict(from_attributes=True)