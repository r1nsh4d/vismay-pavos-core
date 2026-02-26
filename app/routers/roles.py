# app/routes/role_permission.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.database import get_db
from app.dependencies import get_current_user
from app.models.permission import Permission, RolePermission
from app.models.role import Role
from app.schemas.common import ResponseModel, PaginatedResponse
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


# ════════════════════════════════════════════════════════
#  PERMISSIONS
# ════════════════════════════════════════════════════════

@router.get("/permissions")
async def list_permissions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    offset = (page - 1) * limit
    total = await db.scalar(select(func.count()).select_from(Permission))
    result = await db.execute(select(Permission).offset(offset).limit(limit))
    perms = [PermissionResponse.model_validate(p).model_dump() for p in result.scalars().all()]

    return PaginatedResponse(
        data=perms,
        message="Permissions fetched successfully",
        limit=limit,
        page=page,
        total=total
    )


@router.get("/permissions/{permission_id}")
async def get_permission(
    permission_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    perm = await db.scalar(select(Permission).where(Permission.id == permission_id))
    if not perm:
        raise AppException(status_code=404, detail="Permission not found", error_code="NOT_FOUND")
    return ResponseModel(
        data=PermissionResponse.model_validate(perm).model_dump(),
        message="Permission fetched successfully",
    )


@router.post("/permissions", status_code=201)
async def create_permission(
    payload: PermissionCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    if await db.scalar(select(Permission).where(Permission.code == payload.code)):
        raise AppException(status_code=409, detail="Permission code already exists", error_code="DUPLICATE_CODE")

    if await db.scalar(select(Permission).where(Permission.name == payload.name)):
        raise AppException(status_code=409, detail="Permission name already exists", error_code="DUPLICATE_NAME")

    perm = Permission(**payload.model_dump())
    db.add(perm)
    await db.flush()
    await db.refresh(perm)

    return ResponseModel(
        data=PermissionResponse.model_validate(perm).model_dump(),
        message="Permission created successfully",
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

    # Duplicate code check if code is being changed
    if payload.code and payload.code != perm.code:
        if await db.scalar(select(Permission).where(Permission.code == payload.code, Permission.id != permission_id)):
            raise AppException(status_code=409, detail="Permission code already exists", error_code="DUPLICATE_CODE")

    # Duplicate name check if name is being changed
    if payload.name and payload.name != perm.name:
        if await db.scalar(select(Permission).where(Permission.name == payload.name, Permission.id != permission_id)):
            raise AppException(status_code=409, detail="Permission name already exists", error_code="DUPLICATE_NAME")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(perm, field, value)

    await db.flush()
    await db.refresh(perm)

    return ResponseModel(
        data=PermissionResponse.model_validate(perm).model_dump(),
        message="Permission updated successfully",
    )


@router.delete("/permissions/{permission_id}")
async def delete_permission(
    permission_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    perm = await db.scalar(select(Permission).where(Permission.id == permission_id))
    if not perm:
        raise AppException(status_code=404, detail="Permission not found", error_code="NOT_FOUND")

    await db.delete(perm)
    await db.flush()

    return ResponseModel(data=[], message="Permission deleted successfully")


# ════════════════════════════════════════════════════════
#  ROLES
# ════════════════════════════════════════════════════════

@router.get("/roles")
async def list_roles(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    tenant_id: int | None = Query(None),
    is_active: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    offset = (page - 1) * limit
    query = select(Role)
    count_query = select(func.count()).select_from(Role)

    if tenant_id is not None:
        query = query.where(Role.tenant_id == tenant_id)
        count_query = count_query.where(Role.tenant_id == tenant_id)
    if is_active is not None:
        query = query.where(Role.is_active == is_active)
        count_query = count_query.where(Role.is_active == is_active)

    total = await db.scalar(count_query)
    result = await db.execute(query.offset(offset).limit(limit))
    roles = [RoleResponse.model_validate(r).model_dump() for r in result.scalars().all()]

    return PaginatedResponse(
        data=roles,
        message="Roles fetched successfully",
        limit=limit,
        page=page,
        total=total
    )


@router.get("/roles/{role_id}")
async def get_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    role = await db.scalar(select(Role).where(Role.id == role_id))
    if not role:
        raise AppException(status_code=404, detail="Role not found", error_code="NOT_FOUND")

    return ResponseModel(
        data=RoleResponse.model_validate(role).model_dump(),
        message="Role fetched successfully",
    )


# ─── Get Permissions of a Role ────────────────────────────────────────────────

@router.get("/roles/{role_id}/permissions")
async def get_role_permissions(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    role = await db.scalar(select(Role).where(Role.id == role_id))
    if not role:
        raise AppException(status_code=404, detail="Role not found", error_code="NOT_FOUND")

    result = await db.execute(
        select(Permission)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role_id)
    )
    perms = [PermissionResponse.model_validate(p).model_dump() for p in result.scalars().all()]

    return ResponseModel(
        data={"role_id": role_id, "permissions": perms},
        message="Role permissions fetched successfully",
    )


@router.post("/roles", status_code=201)
async def create_role(
    payload: RoleCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    # Duplicate name check within same tenant (respects UniqueConstraint)
    existing = await db.scalar(
        select(Role).where(
            Role.tenant_id == payload.tenant_id,
            Role.name == payload.name,
        )
    )
    if existing:
        raise AppException(
            status_code=409,
            detail="Role name already exists for this tenant",
            error_code="DUPLICATE_NAME",
        )

    role = Role(**payload.model_dump())
    db.add(role)
    await db.flush()
    await db.refresh(role)

    return ResponseModel(
        data=RoleResponse.model_validate(role).model_dump(),
        message="Role created successfully",
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

    # Duplicate name check within same tenant if name is changing
    if payload.name and payload.name != role.name:
        duplicate = await db.scalar(
            select(Role).where(
                Role.tenant_id == role.tenant_id,
                Role.name == payload.name,
                Role.id != role_id,
            )
        )
        if duplicate:
            raise AppException(
                status_code=409,
                detail="Role name already exists for this tenant",
                error_code="DUPLICATE_NAME",
            )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(role, field, value)

    await db.flush()
    await db.refresh(role)

    return ResponseModel(
        data=RoleResponse.model_validate(role).model_dump(),
        message="Role updated successfully",
    )


# ─── Activate / Deactivate Role ───────────────────────────────────────────────

@router.patch("/roles/{role_id}/activate")
async def activate_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    role = await db.scalar(select(Role).where(Role.id == role_id))
    if not role:
        raise AppException(status_code=404, detail="Role not found", error_code="NOT_FOUND")
    if role.is_active:
        raise AppException(status_code=400, detail="Role is already active", error_code="ALREADY_ACTIVE")

    role.is_active = True
    await db.flush()

    return ResponseModel(data={"id": role_id, "is_active": True}, message="Role activated successfully")


@router.patch("/roles/{role_id}/deactivate")
async def deactivate_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    role = await db.scalar(select(Role).where(Role.id == role_id))
    if not role:
        raise AppException(status_code=404, detail="Role not found", error_code="NOT_FOUND")
    if not role.is_active:
        raise AppException(status_code=400, detail="Role is already inactive", error_code="ALREADY_INACTIVE")

    role.is_active = False
    await db.flush()

    return ResponseModel(data={"id": role_id, "is_active": False}, message="Role deactivated successfully")


@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    role = await db.scalar(select(Role).where(Role.id == role_id))
    if not role:
        raise AppException(status_code=404, detail="Role not found", error_code="NOT_FOUND")

    await db.delete(role)
    await db.flush()

    return ResponseModel(data=[], message="Role deleted successfully")


# ─── Assign Permissions to Role ───────────────────────────────────────────────

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

    # Validate all permission_ids exist
    if payload.permission_ids:
        found = await db.scalars(
            select(Permission.id).where(Permission.id.in_(payload.permission_ids))
        )
        found_ids = set(found.all())
        missing = set(payload.permission_ids) - found_ids
        if missing:
            raise AppException(
                status_code=404,
                detail=f"Permissions not found: {missing}",
                error_code="PERMISSION_NOT_FOUND",
            )

    # Replace all existing assignments
    await db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
    for perm_id in payload.permission_ids:
        db.add(RolePermission(role_id=role_id, permission_id=perm_id))

    await db.flush()

    return ResponseModel(
        data={"role_id": role_id, "permission_ids": payload.permission_ids},
        message=f"Assigned {len(payload.permission_ids)} permissions to role",
    )