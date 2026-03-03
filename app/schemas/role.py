# ─── Role ─────────────────────────────────────────────────────────────────────
import uuid
from typing import Optional

from app.schemas.base import CamelModel
from app.schemas.permission import PermissionResponse


class RoleCreate(CamelModel):
    name: str
    description: Optional[str] = None
    permission_ids: list[uuid.UUID] = []


class RoleResponse(CamelModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    permissions: list[PermissionResponse] = []