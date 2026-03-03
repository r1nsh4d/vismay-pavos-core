# ─── Permission ───────────────────────────────────────────────────────────────
import uuid
from typing import Optional

from app.schemas.base import CamelModel


class PermissionCreate(CamelModel):
    name: str
    code: str
    description: Optional[str] = None


class PermissionResponse(CamelModel):
    id: uuid.UUID
    name: str
    code: str
    description: Optional[str] = None