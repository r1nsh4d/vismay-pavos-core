from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.security import hash_password, verify_password
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.role import Role
from app.models.tenant import Tenant
from app.schemas.common import ResponseModel
from app.schemas.user import ChangePasswordRequest, UserCreate, UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["Users"])


# ─── List All ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant_id: int | None = Query(None),
    role_id: int | None = Query(None),
    district_id: int | None = Query(None),
    is_active: bool | None = Query(None),
    is_verified: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    offset = (page - 1) * page_size
    query = select(User)
    count_query = select(func.count()).select_from(User)

    if tenant_id is not None:
        query = query.where(User.tenant_id == tenant_id)
        count_query = count_query.where(User.tenant_id == tenant_id)
    if role_id is not None:
        query = query.where(User.role_id == role_id)
        count_query = count_query.where(User.role_id == role_id)
    if district_id is not None:
        query = query.where(User.district_id == district_id)
        count_query = count_query.where(User.district_id == district_id)
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


# ─── List by Tenant ───────────────────────────────────────────────────────────

@router.get("/tenant/{tenant_id}")
async def list_users_by_tenant(
    tenant_id: int,
    role_id: int | None = Query(None),
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    offset = (page - 1) * page_size
    query = select(User).where(User.tenant_id == tenant_id)
    count_query = select(func.count()).select_from(User).where(User.tenant_id == tenant_id)

    if role_id is not None:
        query = query.where(User.role_id == role_id)
        count_query = count_query.where(User.role_id == role_id)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)

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
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise AppException(status_code=404, detail="User not found", error_code="NOT_FOUND")

    return ResponseModel(
        data=UserResponse.model_validate(user).model_dump(),
        message="User fetched successfully",
    )


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
            "role_code": role.code if role else None,
        },
        message="User role fetched successfully",
    )


# ─── Get Tenant of User ───────────────────────────────────────────────────────

@router.get("/{user_id}/tenant")
async def get_user_tenant(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise AppException(status_code=404, detail="User not found", error_code="NOT_FOUND")

    tenant = None
    if user.tenant_id:
        tenant = await db.scalar(select(Tenant).where(Tenant.id == user.tenant_id))

    return ResponseModel(
        data={
            "user_id": user_id,
            "tenant_id": user.tenant_id,
            "tenant_name": tenant.name if tenant else None,
            "tenant_code": tenant.code if tenant else None,
        },
        message="User tenant fetched successfully",
    )


# ─── Create ───────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    # Duplicate checks
    if await db.scalar(select(User).where(User.email == payload.email)):
        raise AppException(status_code=409, detail="Email already registered", error_code="DUPLICATE_EMAIL")

    if await db.scalar(select(User).where(User.username == payload.username)):
        raise AppException(status_code=409, detail="Username already taken", error_code="DUPLICATE_USERNAME")

    # Validate tenant exists
    if payload.tenant_id:
        if not await db.scalar(select(Tenant).where(Tenant.id == payload.tenant_id)):
            raise AppException(status_code=404, detail="Tenant not found", error_code="TENANT_NOT_FOUND")

    # Validate role exists
    if payload.role_id:
        if not await db.scalar(select(Role).where(Role.id == payload.role_id)):
            raise AppException(status_code=404, detail="Role not found", error_code="ROLE_NOT_FOUND")

    user = User(
        **payload.model_dump(exclude={"password"}),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

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
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise AppException(status_code=404, detail="User not found", error_code="NOT_FOUND")

    if payload.email and payload.email != user.email:
        if await db.scalar(select(User).where(User.email == payload.email, User.id != user_id)):
            raise AppException(status_code=409, detail="Email already registered", error_code="DUPLICATE_EMAIL")

    if payload.username and payload.username != user.username:
        if await db.scalar(select(User).where(User.username == payload.username, User.id != user_id)):
            raise AppException(status_code=409, detail="Username already taken", error_code="DUPLICATE_USERNAME")

    if payload.tenant_id:
        if not await db.scalar(select(Tenant).where(Tenant.id == payload.tenant_id)):
            raise AppException(status_code=404, detail="Tenant not found", error_code="TENANT_NOT_FOUND")

    if payload.role_id:
        if not await db.scalar(select(Role).where(Role.id == payload.role_id)):
            raise AppException(status_code=404, detail="Role not found", error_code="ROLE_NOT_FOUND")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    await db.flush()
    await db.refresh(user)

    return ResponseModel(
        data=UserResponse.model_validate(user).model_dump(),
        message="User updated successfully",
    )


# ─── Activate ─────────────────────────────────────────────────────────────────

@router.patch("/{user_id}/activate")
async def activate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise AppException(status_code=404, detail="User not found", error_code="NOT_FOUND")
    if user.is_active:
        raise AppException(status_code=400, detail="User is already active", error_code="ALREADY_ACTIVE")

    user.is_active = True
    await db.flush()

    return ResponseModel(data={"id": user_id, "is_active": True}, message="User activated successfully")


# ─── Deactivate ───────────────────────────────────────────────────────────────

@router.patch("/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
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
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise AppException(status_code=404, detail="User not found", error_code="NOT_FOUND")

    await db.delete(user)
    await db.flush()

    return ResponseModel(data=[], message="User deleted successfully")