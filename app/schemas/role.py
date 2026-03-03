from typing import Optional, List
import uuid

from app.schemas.base import CamelModel


# Role
class RoleCreate(CamelModel):
    name: str
    description: Optional[str] = None

class RoleResponse(CamelModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    permission_codes: List[str] = []  # Derived from role_permissions