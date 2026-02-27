import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional


class DistrictCreate(BaseModel):
    name: str
    state: Optional[str] = None


class DistrictUpdate(BaseModel):
    name: Optional[str] = None
    state: Optional[str] = None


class DistrictResponse(BaseModel):
    # Changed from int to uuid.UUID
    id: uuid.UUID
    name: str
    state: Optional[str]
    created_at: datetime

    # Modern Pydantic v2 configuration
    model_config = ConfigDict(from_attributes=True)