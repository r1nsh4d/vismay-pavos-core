import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional


class PermissionCreate(BaseModel):
    name: str
    code: str
    description: Optional[str] = None


class PermissionUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None


class PermissionResponse(BaseModel):
    # Primary Key moved to UUID
    id: uuid.UUID
    name: str
    code: str
    description: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---- Role Schemas ----

class RoleCreate(BaseModel):
    # Foreign Key moved to UUID
    tenant_id: Optional[uuid.UUID] = None
    name: str
    description: Optional[str] = None
    is_active: bool = True


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class RoleResponse(BaseModel):
    # All IDs moved to UUID
    id: uuid.UUID
    tenant_id: Optional[uuid.UUID]
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssignPermissionsRequest(BaseModel):
    # List of IDs updated to UUID
    permission_ids: list[uuid.UUID]