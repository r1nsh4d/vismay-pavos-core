from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.database import get_db
from app.dependencies import require_roles
from app.schemas.common import CommonResponse, ErrorResponseModel, ResponseModel
from app.schemas.permission import PermissionCreate, PermissionResponse
from app.services import permissions as perm_svc

router = APIRouter(prefix="/permissions", tags=["Permissions"], dependencies=[Depends(require_roles("super_admin", "admin"))])


@router.post("", response_model=CommonResponse)
async def create_permission(perm_in: PermissionCreate, db: AsyncSession = Depends(get_db)):
    if await perm_svc.get_permission_by_code(db, perm_in.code):
        return ErrorResponseModel(code=400, message="Permission code already exists", error={})

    perm = await perm_svc.create_permission(db, perm_in)
    return ResponseModel(data=PermissionResponse.model_validate(perm), message="Permission created")


@router.get("", response_model=CommonResponse)
async def list_permissions(db: AsyncSession = Depends(get_db)):
    perms = await perm_svc.get_all_permissions(db)
    return ResponseModel(data=[PermissionResponse.model_validate(p) for p in perms], message="Permissions fetched")


@router.get("/{permission_id}", response_model=CommonResponse)
async def get_permission(permission_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    perm = await perm_svc.get_permission_by_id(db, permission_id)
    if not perm:
        return ErrorResponseModel(code=404, message="Permission not found", error={})
    return ResponseModel(data=PermissionResponse.model_validate(perm), message="Permission fetched")


@router.put("/{permission_id}", response_model=CommonResponse)
async def update_permission(permission_id: uuid.UUID, perm_in: PermissionCreate, db: AsyncSession = Depends(get_db)):
    perm = await perm_svc.get_permission_by_id(db, permission_id)
    if not perm:
        return ErrorResponseModel(code=404, message="Permission not found", error={})

    conflict = await perm_svc.get_permission_by_code(db, perm_in.code)
    if conflict and conflict.id != permission_id:
        return ErrorResponseModel(code=400, message="Permission code already in use", error={})

    perm = await perm_svc.update_permission(db, perm, perm_in)
    return ResponseModel(data=PermissionResponse.model_validate(perm), message="Permission updated")


@router.delete("/{permission_id}", response_model=CommonResponse)
async def delete_permission(permission_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    perm = await perm_svc.get_permission_by_id(db, permission_id)
    if not perm:
        return ErrorResponseModel(code=404, message="Permission not found", error={})

    await perm_svc.delete_permission(db, perm)
    return ResponseModel(data=None, message="Permission deleted")