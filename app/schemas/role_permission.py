from datetime import datetime
from pydantic import BaseModel


class PermissionCreate(BaseModel):
    name: str
    code: str
    description: str | None = None


class PermissionUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    description: str | None = None


class PermissionResponse(BaseModel):
    id: int
    name: str
    code: str
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---- Role Schemas ----

class RoleCreate(BaseModel):
    tenant_id: int | None = None
    name: str
    description: str | None = None
    is_active: bool = True


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class RoleResponse(BaseModel):
    id: int
    tenant_id: int | None
    name: str
    description: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AssignPermissionsRequest(BaseModel):
    permission_ids: list[int]
