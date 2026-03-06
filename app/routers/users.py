from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid

from app.core.exceptions import AppException
from app.database import get_db
from app.schemas.user import UserCreate, UserUpdate
from app.schemas.common import CommonResponse, ErrorResponseModel, ResponseModel, PaginatedResponse
from app.services import users as user_mgmt
from app.dependencies import get_current_user, require_roles, require_permissions


router = APIRouter(prefix="/users", tags=["Users"], dependencies=[Depends(require_roles("super_admin", "admin"))])


@router.post("", response_model=CommonResponse)
async def create_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    if await user_mgmt.get_user_by_username_or_email(db, user_in.username, user_in.email):
        raise AppException(status_code=400, detail="Username or email already exists")
    user = await user_mgmt.create_user(db, user_in)
    await db.commit()
    return ResponseModel(data=user_mgmt.serialize_user(user), message="User created successfully")


@router.get("", response_model=CommonResponse)
async def list_users(
    is_active: bool | None = None,
    role_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    district_id: uuid.UUID | None = None,
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    users, total = await user_mgmt.get_all_users(
        db, is_active=is_active, role_id=role_id,
        tenant_id=tenant_id, district_id=district_id,
        page=page, limit=limit,
    )
    return PaginatedResponse(
        data=[user_mgmt.serialize_user(u) for u in users],
        message="Users fetched successfully",
        page=page,
        limit=limit,
        total=total,
    )


@router.get("/{user_id}", response_model=CommonResponse)
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    user = await user_mgmt.get_user_by_id(db, user_id)
    if not user:
        raise AppException(status_code=404, detail="User not found")
    return ResponseModel(data=user_mgmt.serialize_user(user), message="User fetched successfully")


@router.put("/{user_id}", response_model=CommonResponse)
async def update_user(user_id: uuid.UUID, user_in: UserUpdate, db: AsyncSession = Depends(get_db)):
    user = await user_mgmt.get_user_by_id(db, user_id)
    if not user:
        raise AppException(status_code=404, detail="User not found")
    user = await user_mgmt.update_user(db, user, user_in)
    return ResponseModel(data=user_mgmt.serialize_user(user), message="User updated successfully")


@router.delete("/{user_id}", response_model=CommonResponse)
async def delete_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    user = await user_mgmt.get_user_by_id(db, user_id)
    if not user:
        raise AppException(status_code=404, detail="User not found")
    await user_mgmt.delete_user(db, user)
    return ResponseModel(data=None, message="User deleted successfully")


@router.patch("/{user_id}/role", response_model=CommonResponse)
async def assign_role(user_id: uuid.UUID, role_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    user = await user_mgmt.get_user_by_id(db, user_id)
    if not user:
        raise AppException(status_code=404, detail="User not found")
    user = await user_mgmt.assign_role(db, user, role_id)
    if not user:
        raise AppException(status_code=404, detail="Role not found")
    return ResponseModel(data=user_mgmt.serialize_user(user), message="Role assigned successfully")


@router.delete("/{user_id}/role", response_model=CommonResponse)
async def remove_role(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    user = await user_mgmt.get_user_by_id(db, user_id)
    if not user:
        raise AppException(status_code=404, detail="User not found")
    user = await user_mgmt.remove_role(db, user)
    return ResponseModel(data=user_mgmt.serialize_user(user), message="Role removed successfully")


@router.post("/{user_id}/tenants", response_model=CommonResponse)
async def assign_tenants(user_id: uuid.UUID, tenant_ids: List[uuid.UUID], db: AsyncSession = Depends(get_db)):
    user = await user_mgmt.get_user_by_id(db, user_id)
    if not user:
        raise AppException(status_code=404, detail="User not found")
    result = await user_mgmt.assign_tenants(db, user, tenant_ids)
    return ResponseModel(data=result, message="Tenants assigned successfully")


@router.delete("/{user_id}/tenants/{tenant_id}", response_model=CommonResponse)
async def remove_tenant(user_id: uuid.UUID, tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    removed = await user_mgmt.remove_tenant(db, user_id, tenant_id)
    if not removed:
        raise AppException(status_code=404, detail="User-Tenant assignment not found")
    return ResponseModel(data=None, message="Tenant removed from user")


@router.patch("/{user_id}/tenants/{tenant_id}/toggle", response_model=CommonResponse)
async def toggle_user_tenant(user_id: uuid.UUID, tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    ut = await user_mgmt.toggle_user_tenant(db, user_id, tenant_id)
    if not ut:
        raise AppException(status_code=404, detail="User-Tenant assignment not found")
    status = "activated" if ut.is_active else "deactivated"
    return ResponseModel(data=None, message=f"User-Tenant {status}")


@router.post("/{user_id}/districts", response_model=CommonResponse)
async def assign_districts(user_id: uuid.UUID, district_ids: List[uuid.UUID], db: AsyncSession = Depends(get_db)):
    user = await user_mgmt.get_user_by_id(db, user_id)
    if not user:
        raise AppException(status_code=404, detail="User not found")
    result = await user_mgmt.assign_districts(db, user, district_ids)
    return ResponseModel(data=result, message="Districts assigned successfully")


@router.delete("/{user_id}/districts/{district_id}", response_model=CommonResponse)
async def remove_district(user_id: uuid.UUID, district_ids: list[uuid.UUID], db: AsyncSession = Depends(get_db)):
    removed = await user_mgmt.remove_districts(db, user_id, district_ids)
    if not removed:
        raise AppException(status_code=404, detail="User-District assignment not found")
    return ResponseModel(data=None, message="District removed from user")


@router.patch("/{user_id}/districts/{district_id}/toggle", response_model=CommonResponse)
async def toggle_user_district(user_id: uuid.UUID, district_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    ud = await user_mgmt.toggle_user_district(db, user_id, district_id)
    if not ud:
        raise AppException(status_code=404, detail="User-District assignment not found")
    status = "activated" if ud.is_active else "deactivated"
    return ResponseModel(data=None, message=f"User-District {status}")


@router.patch("/{user_id}/verify", response_model=CommonResponse)
async def verify_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    user = await user_mgmt.get_user_by_id(db, user_id)
    if not user:
        raise AppException(status_code=404, detail="User not found")
    await user_mgmt.verify_user(db, user)
    return ResponseModel(data=None, message="User verified successfully")


@router.patch("/{user_id}/toggle", response_model=CommonResponse)
async def toggle_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    user = await user_mgmt.get_user_by_id(db, user_id)
    if not user:
        raise AppException(status_code=404, detail="User not found")
    user = await user_mgmt.toggle_user_active(db, user)
    status = "activated" if user.is_active else "deactivated"
    return ResponseModel(data=None, message=f"User {status} successfully")


@router.patch("/{user_id}/reset-password", response_model=CommonResponse)
async def reset_password(user_id: uuid.UUID, new_password: str, db: AsyncSession = Depends(get_db)):
    user = await user_mgmt.get_user_by_id(db, user_id)
    if not user:
        raise AppException(status_code=404, detail="User not found")
    await user_mgmt.reset_password(db, user, new_password)
    return ResponseModel(data=None, message="Password reset successfully")