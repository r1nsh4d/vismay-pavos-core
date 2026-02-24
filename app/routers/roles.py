from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.database import get_db
from app.dependencies import get_current_user
from app.models.permission import Permission, RolePermission
from app.models.role import Role
from app.schemas.common import ResponseModel
from app.schemas.role_permission import (
    AssignPermissionsRequest,
    PermissionCreate,
    PermissionResponse,
    PermissionUpdate,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
)

router = APIRouter(tags=["Roles & Permissions"])


# ─── Permissions ─────────────────────────────────────────────────────────────

@router.get("/permissions")
async def list_permissions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    offset = (page - 1) * page_size
    total = await db.scalar(select(func.count()).select_from(Permission))
    result = await db.execute(select(Permission).offset(offset).limit(page_size))
    perms = [PermissionResponse.model_validate(p).model_dump() for p in result.scalars().all()]
    return ResponseModel(
        data={"total": total, "page": page, "page_size": page_size, "results": perms},
        message="Permissions fetched successfully",
    )


@router.post("/permissions", status_code=201)
async def create_permission(
    payload: PermissionCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    existing = await db.scalar(select(Permission).where(Permission.code == payload.code))
    if existing:
        raise AppException(status_code=409, detail="Permission code already exists", error_code="DUPLICATE_CODE")
    perm = Permission(**payload.model_dump())
    db.add(perm)
    await db.flush()
    await db.refresh(perm)
    return ResponseModel(
        data=PermissionResponse.model_validate(perm).model_dump(),
        message="Permission created successfully",
    )


@router.get("/permissions/{permission_id}")
async def get_permission(permission_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    perm = await db.scalar(select(Permission).where(Permission.id == permission_id))
    if not perm:
        raise AppException(status_code=404, detail="Permission not found", error_code="NOT_FOUND")
    return ResponseModel(
        data=PermissionResponse.model_validate(perm).model_dump(),
        message="Permission fetched successfully",
    )


@router.patch("/permissions/{permission_id}")
async def update_permission(
    permission_id: int,
    payload: PermissionUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    perm = await db.scalar(select(Permission).where(Permission.id == permission_id))
    if not perm:
        raise AppException(status_code=404, detail="Permission not found", error_code="NOT_FOUND")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(perm, field, value)
    await db.flush()
    await db.refresh(perm)
    return ResponseModel(
        data=PermissionResponse.model_validate(perm).model_dump(),
        message="Permission updated successfully",
    )


@router.delete("/permissions/{permission_id}")
async def delete_permission(permission_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    perm = await db.scalar(select(Permission).where(Permission.id == permission_id))
    if not perm:
        raise AppException(status_code=404, detail="Permission not found", error_code="NOT_FOUND")
    await db.delete(perm)
    await db.flush()
    return ResponseModel(data=[], message="Permission deleted successfully")


# ─── Roles ──────────────────────────────────────────────────────────────────

@router.get("/roles")
async def list_roles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    offset = (page - 1) * page_size
    query = select(Role)
    count_query = select(func.count()).select_from(Role)
    if tenant_id:
        query = query.where(Role.tenant_id == tenant_id)
        count_query = count_query.where(Role.tenant_id == tenant_id)
    total = await db.scalar(count_query)
    result = await db.execute(query.offset(offset).limit(page_size))
    roles = [RoleResponse.model_validate(r).model_dump() for r in result.scalars().all()]
    return ResponseModel(
        data={"total": total, "page": page, "page_size": page_size, "results": roles},
        message="Roles fetched successfully",
    )


@router.post("/roles", status_code=201)
async def create_role(
    payload: RoleCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    role = Role(**payload.model_dump())
    db.add(role)
    await db.flush()
    await db.refresh(role)
    return ResponseModel(
        data=RoleResponse.model_validate(role).model_dump(),
        message="Role created successfully",
    )


@router.get("/roles/{role_id}")
async def get_role(role_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    role = await db.scalar(select(Role).where(Role.id == role_id))
    if not role:
        raise AppException(status_code=404, detail="Role not found", error_code="NOT_FOUND")
    return ResponseModel(
        data=RoleResponse.model_validate(role).model_dump(),
        message="Role fetched successfully",
    )


@router.patch("/roles/{role_id}")
async def update_role(
    role_id: int,
    payload: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    role = await db.scalar(select(Role).where(Role.id == role_id))
    if not role:
        raise AppException(status_code=404, detail="Role not found", error_code="NOT_FOUND")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(role, field, value)
    await db.flush()
    await db.refresh(role)
    return ResponseModel(
        data=RoleResponse.model_validate(role).model_dump(),
        message="Role updated successfully",
    )


@router.delete("/roles/{role_id}")
async def delete_role(role_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    role = await db.scalar(select(Role).where(Role.id == role_id))
    if not role:
        raise AppException(status_code=404, detail="Role not found", error_code="NOT_FOUND")
    await db.delete(role)
    await db.flush()
    return ResponseModel(data=[], message="Role deleted successfully")


@router.post("/roles/{role_id}/permissions")
async def assign_permissions_to_role(
    role_id: int,
    payload: AssignPermissionsRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    role = await db.scalar(select(Role).where(Role.id == role_id))
    if not role:
        raise AppException(status_code=404, detail="Role not found", error_code="NOT_FOUND")

    existing = await db.execute(select(RolePermission).where(RolePermission.role_id == role_id))
    for rp in existing.scalars().all():
        await db.delete(rp)

    for perm_id in payload.permission_ids:
        db.add(RolePermission(role_id=role_id, permission_id=perm_id))

    await db.flush()
    return ResponseModel(
        data={"role_id": role_id, "permission_ids": payload.permission_ids},
        message=f"Assigned {len(payload.permission_ids)} permissions to role",
    )
