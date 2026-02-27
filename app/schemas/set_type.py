import uuid
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class SetTypeDetailCreate(BaseModel):
    # Field 'example' updated to 'examples' for Pydantic v2 compliance
    value: str = Field(..., examples=["M"], description="Size value e.g. M, L, XL, XXL")


class SetTypeDetailResponse(BaseModel):
    # Primary and Foreign keys changed to UUID
    id: uuid.UUID
    set_type_id: uuid.UUID
    value: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class SetTypeCreate(BaseModel):
    # Updated to UUIDs
    tenant_id: uuid.UUID = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])
    category_id: uuid.UUID = Field(..., examples=["71502258-2aac-4108-a84a-f5954db48b0d"])
    name: str = Field(..., examples=["A SET"])
    piece_count: int | None = Field(None, examples=[4])
    description: str | None = Field(None, examples=["A set with 4 sizes"])
    is_active: bool = Field(True)
    details: list[SetTypeDetailCreate] = Field(
        examples=[
            [{"value": "M"}, {"value": "L"}, {"value": "XL"}, {"value": "XXL"}]
        ]
    )


class SetTypeUpdate(BaseModel):
    name: str | None = None
    piece_count: int | None = None
    description: str | None = None
    is_active: bool | None = None


class SetTypeResponse(BaseModel):
    # All IDs updated to UUID
    id: uuid.UUID
    tenant_id: uuid.UUID
    category_id: uuid.UUID
    name: str
    piece_count: int | None
    description: str | None
    is_active: bool
    created_at: datetime
    details: list[SetTypeDetailResponse] = []
    
    model_config = ConfigDict(from_attributes=True)