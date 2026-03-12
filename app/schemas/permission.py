from typing import Optional, List
import uuid

from app.schemas.base import CamelModel


# Permission
class PermissionCreate(CamelModel):
    name: str
    code: str
    description: Optional[str] = None


class PermissionResponse(CamelModel):
    id: uuid.UUID
    name: str
    code: str
    description: Optional[str] = None