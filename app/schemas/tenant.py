# ─── Tenant ───────────────────────────────────────────────────────────────────
import uuid

from app.schemas.base import CamelModel


class TenantCreate(CamelModel):
    name: str
    code: str


class TenantResponse(CamelModel):
    id: uuid.UUID
    name: str
    code: str
    is_active: bool