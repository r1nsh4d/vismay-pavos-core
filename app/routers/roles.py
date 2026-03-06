from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid

from app.core.exceptions import AppException
from app.database import get_db
from app.dependencies import require_roles
from app.schemas.common import CommonResponse, ErrorResponseModel, ResponseModel, PaginatedResponse
from app.schemas.role import RoleCreate
from app.services import roles as role_mgmt

router = APIRouter(prefix="/roles", tags=["Roles"], dependencies=[Depends(require_roles("super_admin","admin"))])


@router.post("", response_model=CommonResponse)
async def create_role(role_in: RoleCreate, db: AsyncSession = Depends(get_db)):
    if await role_mgmt.get_role_by_name(db, role_in.name):
        raise AppException(status_code=400, detail="Role name already exists")

    role = await role_mgmt.create_role(db, role_in)
    return ResponseModel(data=role_mgmt.serialize_role(role), message="Role created successfully")


@router.get("", response_model=CommonResponse)
async def list_roles(
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    roles, total = await role_mgmt.get_all_roles(db, page=page, limit=limit)
    return PaginatedResponse(
        data=[role_mgmt.serialize_role(r) for r in roles],
        message="Roles fetched successfully",
        page=page,
        limit=limit,
        total=total,
    )

@router.get("/{role_id}", response_model=CommonResponse)
async def get_role(role_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    role = await role_mgmt.get_role_by_id(db, role_id)
    if not role:
        raise AppException(status_code=404, detail="Role not found")
    return ResponseModel(data=role_mgmt.serialize_role(role), message="Role fetched successfully")


@router.put("/{role_id}", response_model=CommonResponse)
async def update_role(role_id: uuid.UUID, role_in: RoleCreate, db: AsyncSession = Depends(get_db)):
    role = await role_mgmt.get_role_by_id(db, role_id)
    if not role:
        raise AppException(status_code=404, detail="Role not found")

    role = await role_mgmt.update_role(db, role, role_in)
    return ResponseModel(data=role_mgmt.serialize_role(role), message="Role updated successfully")


@router.delete("/{role_id}", response_model=CommonResponse)
async def delete_role(role_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    role = await role_mgmt.get_role_by_id(db, role_id)
    if not role:
        raise AppException(status_code=404, detail="Role not found")

    await role_mgmt.delete_role(db, role)
    return ResponseModel(data=None, message="Role deleted successfully")


@router.post("/{role_id}/permissions", response_model=CommonResponse)
async def assign_permissions(
    role_id: uuid.UUID, permission_ids: List[uuid.UUID], db: AsyncSession = Depends(get_db)
):
    role = await role_mgmt.get_role_by_id(db, role_id)
    if not role:
        raise AppException(status_code=404, detail="Role not found")

    result = await role_mgmt.assign_permissions_to_role(db, role, permission_ids)
    # Re-fetch role to get updated permissions for serialization
    role = await role_mgmt.get_role_by_id(db, role_id)
    return ResponseModel(data={**result, "role": role_mgmt.serialize_role(role)}, message="Permissions assigned")


@router.delete("/{role_id}/permissions/{permission_id}", response_model=CommonResponse)
async def remove_permission(
    role_id: uuid.UUID, permission_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    removed = await role_mgmt.remove_permission_from_role(db, role_id, permission_id)
    if not removed:
        raise AppException(status_code=404, detail="Permission assignment not found")
    return ResponseModel(data=None, message="Permission removed from role")