from datetime import datetime
from pydantic import BaseModel


class DistrictCreate(BaseModel):
    name: str
    state: str | None = None


class DistrictUpdate(BaseModel):
    name: str | None = None
    state: str | None = None


class DistrictResponse(BaseModel):
    id: int
    name: str
    state: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
