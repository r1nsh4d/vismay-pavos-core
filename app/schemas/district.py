# ─── District ─────────────────────────────────────────────────────────────────
import uuid

from app.schemas.base import CamelModel


class DistrictCreate(CamelModel):
    name: str
    state: str


class DistrictResponse(CamelModel):
    id: uuid.UUID
    name: str
    state: str