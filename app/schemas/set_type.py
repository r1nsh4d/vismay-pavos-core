from pydantic import BaseModel, Field
from datetime import datetime


class SetTypeDetailCreate(BaseModel):
    value: str = Field(..., example="M", description="Size value e.g. M, L, XL, XXL")


class SetTypeDetailResponse(BaseModel):
    id: int
    set_type_id: int
    value: str
    created_at: datetime
    model_config = {"from_attributes": True}


class SetTypeCreate(BaseModel):
    tenant_id: int = Field(..., example=1)
    category_id: int = Field(..., example=2)
    name: str = Field(..., example="A SET")
    piece_count: int | None = Field(None, example=4)
    description: str | None = Field(None, example="A set with 4 sizes")
    is_active: bool = Field(True)
    details: list[SetTypeDetailCreate] = Field(
        example=[
            {"value": "M"},
            {"value": "L"},
            {"value": "XL"},
            {"value": "XXL"},
        ]
    )


class SetTypeUpdate(BaseModel):
    name: str | None = None
    piece_count: int | None = None
    description: str | None = None
    is_active: bool | None = None


class SetTypeResponse(BaseModel):
    id: int
    tenant_id: int
    category_id: int
    name: str
    piece_count: int | None
    description: str | None
    is_active: bool
    created_at: datetime
    details: list[SetTypeDetailResponse] = []
    model_config = {"from_attributes": True}