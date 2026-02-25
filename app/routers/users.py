from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.core.security import hash_password, verify_password
from app.database import get_db
from app.dependencies import get_current_user
from app.models import RolePermission
from app.models.district import District
from app.models.role import Role
from app.models.tenant import Tenant
from app.models.user import User, UserDistrict, UserTenant
from app.schemas.common import ResponseModel
from app.schemas.user import (
    AssignDistrictsRequest,
    AssignTenantsRequest,
    ChangePasswordRequest,
    UserCreate,
    UserResponse,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["Users"])


# ─── Helper ───────────────────────────────────────────────────────────────────

async def _get_user_with_relations(db: AsyncSession, user: User) -> User:
    """Reload user with tenants, districts and role for response."""
    user_id = user if isinstance(user, int) else user.id  # ← handle both
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.role)
                .selectinload(Role.role_permissions)
                .selectinload(RolePermission.permission),  # ← load permissions
            selectinload(User.user_tenants).selectinload(UserTenant.tenant),
            selectinload(User.user_districts).selectinload(UserDistrict.district),
        )
        .where(User.id == user_id)
    )
    return result.scalar_one()


# ─── List All ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant_id: int | None = Query(None),
    district_id: int | None = Query(None),
    role_id: int | None = Query(None),
    is_active: bool | None = Query(None),
    is_verified: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    offset = (page - 1) * page_size
    query = select(User).options(
        selectinload(User.role)
        .selectinload(Role.role_permissions)
        .selectinload(RolePermission.permission),  # ← add this
        selectinload(User.user_tenants).selectinload(UserTenant.tenant),
        selectinload(User.user_districts).selectinload(UserDistrict.district),
    )
    count_query = select(func.count()).select_from(User)

    if tenant_id is not None:
        query = query.join(UserTenant).where(UserTenant.tenant_id == tenant_id)
        count_query = count_query.join(UserTenant).where(UserTenant.tenant_id == tenant_id)
    if district_id is not None:
        query = query.join(UserDistrict).where(UserDistrict.district_id == district_id)
        count_query = count_query.join(UserDistrict).where(UserDistrict.district_id == district_id)
    if role_id is not None:
        query = query.where(User.role_id == role_id)
        count_query = count_query.where(User.role_id == role_id)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)
    if is_verified is not None:
        query = query.where(User.is_verified == is_verified)
        count_query = count_query.where(User.is_verified == is_verified)

    total = await db.scalar(count_query)
    result = await db.execute(query.offset(offset).limit(page_size))
    users = [UserResponse.model_validate(u).model_dump() for u in result.scalars().all()]

    return ResponseModel(
        data={"total": total, "page": page, "page_size": page_size, "results": users},
        message="Users fetched successfully",
    )


# ─── Get by ID ────────────────────────────────────────────────────────────────

@router.get("/{user_id}")
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    user = await _get_user_with_relations(db, user_id)
    if not user:
        raise AppException(status_code=404, detail="User not found", error_code="NOT_FOUND")

    return ResponseModel(
        data=UserResponse.model_validate(user).model_dump(),
        message="User fetched successfully",
    )


# ─── Get Tenants of User ──────────────────────────────────────────────────────

@router.get("/{user_id}/tenants")
async def get_user_tenants(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise AppException(status_code=404, detail="User not found", error_code="NOT_FOUND")

    result = await db.execute(
        select(UserTenant, Tenant)
        .join(Tenant, Tenant.id == UserTenant.tenant_id)
        .where(UserTenant.user_id == user_id)
    )
    data = [
        {
            "user_tenant_id": ut.id,
            "tenant_id": t.id,
            "tenant_name": t.name,
            "tenant_code": t.code,
            "is_active": ut.is_active,
        }
        for ut, t in result.all()
    ]

    return ResponseModel(data=data, message="User tenants fetched successfully")


# ─── Get Districts of User ────────────────────────────────────────────────────

@router.get("/{user_id}/districts")
async def get_user_districts(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise AppException(status_code=404, detail="User not found", error_code="NOT_FOUND")

    result = await db.execute(
        select(UserDistrict, District)
        .join(District, District.id == UserDistrict.district_id)
        .where(UserDistrict.user_id == user_id)
    )
    data = [
        {
            "user_district_id": ud.id,
            "district_id": d.id,
            "district_name": d.name,
            "state": d.state,
            "is_active": ud.is_active,
        }
        for ud, d in result.all()
    ]

    return ResponseModel(data=data, message="User districts fetched successfully")


# ─── Get Role of User ─────────────────────────────────────────────────────────

@router.get("/{user_id}/role")
async def get_user_role(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise AppException(status_code=404, detail="User not found", error_code="NOT_FOUND")

    role = None
    if user.role_id:
        role = await db.scalar(select(Role).where(Role.id == user.role_id))

    return ResponseModel(
        data={
            "user_id": user_id,
            "role_id": user.role_id,
            "role_name": role.name if role else None,
        },
        message="User role fetched successfully",
    )


# ─── Create ───────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    if await db.scalar(select(User).where(User.email == payload.email)):
        raise AppException(status_code=409, detail="Email already registered", error_code="DUPLICATE_EMAIL")

    if await db.scalar(select(User).where(User.username == payload.username)):
        raise AppException(status_code=409, detail="Username already taken", error_code="DUPLICATE_USERNAME")

    if payload.role_id:
        if not await db.scalar(select(Role).where(Role.id == payload.role_id)):
            raise AppException(status_code=404, detail="Role not found", error_code="ROLE_NOT_FOUND")

    # Validate tenant_ids
    if payload.tenant_ids:
        found = set((await db.scalars(select(Tenant.id).where(Tenant.id.in_(payload.tenant_ids)))).all())
        missing = set(payload.tenant_ids) - found
        if missing:
            raise AppException(status_code=404, detail=f"Tenants not found: {missing}", error_code="TENANT_NOT_FOUND")

    # Validate district_ids
    if payload.district_ids:
        found = set((await db.scalars(select(District.id).where(District.id.in_(payload.district_ids)))).all())
        missing = set(payload.district_ids) - found
        if missing:
            raise AppException(status_code=404, detail=f"Districts not found: {missing}", error_code="DISTRICT_NOT_FOUND")

    user = User(
        **payload.model_dump(exclude={"password", "tenant_ids", "district_ids"}),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    await db.flush()

    for tid in payload.tenant_ids:
        db.add(UserTenant(user_id=user.id, tenant_id=tid))
    for did in payload.district_ids:
        db.add(UserDistrict(user_id=user.id, district_id=did))
    await db.flush()

    user = await _get_user_with_relations(db, user.id)

    return ResponseModel(
        data=UserResponse.model_validate(user).model_dump(),
        message="User created successfully",
    )


# ─── Update ───────────────────────────────────────────────────────────────────

@router.patch("/{user_id}")
async def update_user(
    user_id: int,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    user = await _get_user_with_relations(db, user_id)
    if not user:
        raise AppException(status_code=404, detail="User not found", error_code="NOT_FOUND")

    if payload.email and payload.email != user.email:
        if await db.scalar(select(User).where(User.email == payload.email, User.id != user_id)):
            raise AppException(status_code=409, detail="Email already registered", error_code="DUPLICATE_EMAIL")

    if payload.username and payload.username != user.username:
        if await db.scalar(select(User).where(User.username == payload.username, User.id != user_id)):
            raise AppException(status_code=409, detail="Username already taken", error_code="DUPLICATE_USERNAME")

    if payload.role_id:
        if not await db.scalar(select(Role).where(Role.id == payload.role_id)):
            raise AppException(status_code=404, detail="Role not found", error_code="ROLE_NOT_FOUND")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    await db.flush()

    # ← reload with relations instead of db.refresh
    user = await _get_user_with_relations(db, user_id)

    return ResponseModel(
        data=UserResponse.model_validate(user).model_dump(),
        message="User updated successfully",
    )


# ─── Assign / Replace Tenants ─────────────────────────────────────────────────

@router.put("/{user_id}/tenants")
async def assign_tenants(
    user_id: int,
    payload: AssignTenantsRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    if not await db.scalar(select(User).where(User.id == user_id)):
        raise AppException(status_code=404, detail="User not found", error_code="NOT_FOUND")

    if payload.tenant_ids:
        found = set((await db.scalars(select(Tenant.id).where(Tenant.id.in_(payload.tenant_ids)))).all())
        missing = set(payload.tenant_ids) - found
        if missing:
            raise AppException(status_code=404, detail=f"Tenants not found: {missing}", error_code="TENANT_NOT_FOUND")

    await db.execute(delete(UserTenant).where(UserTenant.user_id == user_id))
    for tid in payload.tenant_ids:
        db.add(UserTenant(user_id=user_id, tenant_id=tid))
    await db.flush()

    return ResponseModel(
        data={"user_id": user_id, "tenant_ids": payload.tenant_ids},
        message="Tenants assigned successfully",
    )


# ─── Assign / Replace Districts ───────────────────────────────────────────────

@router.put("/{user_id}/districts")
async def assign_districts(
    user_id: int,
    payload: AssignDistrictsRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    if not await db.scalar(select(User).where(User.id == user_id)):
        raise AppException(status_code=404, detail="User not found", error_code="NOT_FOUND")

    if payload.district_ids:
        found = set((await db.scalars(select(District.id).where(District.id.in_(payload.district_ids)))).all())
        missing = set(payload.district_ids) - found
        if missing:
            raise AppException(status_code=404, detail=f"Districts not found: {missing}", error_code="DISTRICT_NOT_FOUND")

    await db.execute(delete(UserDistrict).where(UserDistrict.user_id == user_id))
    for did in payload.district_ids:
        db.add(UserDistrict(user_id=user_id, district_id=did))
    await db.flush()

    return ResponseModel(
        data={"user_id": user_id, "district_ids": payload.district_ids},
        message="Districts assigned successfully",
    )


# ─── Activate / Deactivate ────────────────────────────────────────────────────

@router.patch("/{user_id}/activate")
async def activate_user(user_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise AppException(status_code=404, detail="User not found", error_code="NOT_FOUND")
    if user.is_active:
        raise AppException(status_code=400, detail="User is already active", error_code="ALREADY_ACTIVE")
    user.is_active = True
    await db.flush()
    return ResponseModel(data={"id": user_id, "is_active": True}, message="User activated successfully")


@router.patch("/{user_id}/deactivate")
async def deactivate_user(user_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise AppException(status_code=404, detail="User not found", error_code="NOT_FOUND")
    if not user.is_active:
        raise AppException(status_code=400, detail="User is already inactive", error_code="ALREADY_INACTIVE")
    user.is_active = False
    await db.flush()
    return ResponseModel(data={"id": user_id, "is_active": False}, message="User deactivated successfully")


# ─── Change Password ──────────────────────────────────────────────────────────

@router.patch("/{user_id}/change-password")
async def change_password(
    user_id: int,
    payload: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise AppException(status_code=404, detail="User not found", error_code="NOT_FOUND")
    if not verify_password(payload.old_password, user.password_hash):
        raise AppException(status_code=400, detail="Old password is incorrect", error_code="INVALID_PASSWORD")
    user.password_hash = hash_password(payload.new_password)
    await db.flush()
    return ResponseModel(data=[], message="Password changed successfully")


# ─── Delete ───────────────────────────────────────────────────────────────────

@router.delete("/{user_id}")
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise AppException(status_code=404, detail="User not found", error_code="NOT_FOUND")
    await db.delete(user)
    await db.flush()
    return ResponseModel(data=[], message="User deleted successfully")