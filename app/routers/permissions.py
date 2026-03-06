from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.core.exceptions import AppException
from app.database import get_db
from app.dependencies import require_roles
from app.schemas.common import CommonResponse, ErrorResponseModel, ResponseModel, PaginatedResponse
from app.schemas.permission import PermissionCreate, PermissionResponse
from app.services import permissions as permission_mgmt

router = APIRouter(prefix="/permissions", tags=["Permissions"], dependencies=[Depends(require_roles("super_admin", "admin"))])


@router.post("", response_model=CommonResponse)
async def create_permission(perm_in: PermissionCreate, db: AsyncSession = Depends(get_db)):
    if await permission_mgmt.get_permission_by_code(db, perm_in.code):
        raise AppException(status_code=400, detail="Permission code already exists")

    perm = await permission_mgmt.create_permission(db, perm_in)
    return ResponseModel(data=PermissionResponse.model_validate(perm), message="Permission created")


@router.get("", response_model=CommonResponse)
async def list_permissions(
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    perms, total = await permission_mgmt.get_all_permissions(db, page=page, limit=limit)
    return PaginatedResponse(
        data=[PermissionResponse.model_validate(p) for p in perms],
        message="Permissions fetched",
        page=page,
        limit=limit,
        total=total,
    )


@router.get("/{permission_id}", response_model=CommonResponse)
async def get_permission(permission_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    perm = await permission_mgmt.get_permission_by_id(db, permission_id)
    if not perm:
        raise AppException(status_code=404, detail="Permission not found")
    return ResponseModel(data=PermissionResponse.model_validate(perm), message="Permission fetched")


@router.put("/{permission_id}", response_model=CommonResponse)
async def update_permission(permission_id: uuid.UUID, perm_in: PermissionCreate, db: AsyncSession = Depends(get_db)):
    perm = await permission_mgmt.get_permission_by_id(db, permission_id)
    if not perm:
        raise AppException(status_code=404, detail="Permission not found")
    conflict = await permission_mgmt.get_permission_by_code(db, perm_in.code)
    if conflict and conflict.id != permission_id:
        raise AppException(status_code=400, detail="Permission code already in use")
    perm = await permission_mgmt.update_permission(db, perm, perm_in)
    return ResponseModel(data=PermissionResponse.model_validate(perm), message="Permission updated")


@router.delete("/{permission_id}", response_model=CommonResponse)
async def delete_permission(permission_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    perm = await permission_mgmt.get_permission_by_id(db, permission_id)
    if not perm:
        raise AppException(status_code=404, detail="Permission not found")
    await permission_mgmt.delete_permission(db, perm)
    return ResponseModel(data=None, message="Permission deleted")