from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.database import get_db
from app.schemas.user import UserCreate, UserUpdate
from app.schemas.common import CommonResponse, ErrorResponseModel, ResponseModel
from app.services import users as user_mgmt

router = APIRouter(prefix="/users", tags=["Users"])


# ── CRUD ───────────────────────────────────────────────────────────────────────

@router.post("", response_model=CommonResponse)
def create_user(user_in: UserCreate, db: Session = Depends(get_db)):
    if user_mgmt.get_user_by_username_or_email(db, user_in.username, user_in.email):
        return ErrorResponseModel(code=400, message="Username or email already exists", error={})

    user = user_mgmt.create_user(db, user_in)
    return ResponseModel(data=user_mgmt.serialize_user(user), message="User created successfully")


@router.get("", response_model=CommonResponse)
def list_users(
    is_active: bool | None = None,
    role_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    district_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
):
    users = user_mgmt.get_all_users(db, is_active=is_active, role_id=role_id,
                                    tenant_id=tenant_id, district_id=district_id)
    return ResponseModel(data=[user_mgmt.serialize_user(u) for u in users], message="Users fetched successfully")


@router.get("/{user_id}", response_model=CommonResponse)
def get_user(user_id: uuid.UUID, db: Session = Depends(get_db)):
    user = user_mgmt.get_user_by_id(db, user_id)
    if not user:
        return ErrorResponseModel(code=404, message="User not found", error={})
    return ResponseModel(data=user_mgmt.serialize_user(user), message="User fetched successfully")


@router.put("/{user_id}", response_model=CommonResponse)
def update_user(user_id: uuid.UUID, user_in: UserUpdate, db: Session = Depends(get_db)):
    user = user_mgmt.get_user_by_id(db, user_id)
    if not user:
        return ErrorResponseModel(code=404, message="User not found", error={})

    user = user_mgmt.update_user(db, user, user_in)
    return ResponseModel(data=user_mgmt.serialize_user(user), message="User updated successfully")


@router.delete("/{user_id}", response_model=CommonResponse)
def delete_user(user_id: uuid.UUID, db: Session = Depends(get_db)):
    user = user_mgmt.get_user_by_id(db, user_id)
    if not user:
        return ErrorResponseModel(code=404, message="User not found", error={})

    user_mgmt.delete_user(db, user)
    return ResponseModel(data=None, message="User deleted successfully")


# ── Role ───────────────────────────────────────────────────────────────────────

@router.patch("/{user_id}/role", response_model=CommonResponse)
def assign_role(user_id: uuid.UUID, role_id: uuid.UUID, db: Session = Depends(get_db)):
    user = user_mgmt.get_user_by_id(db, user_id)
    if not user:
        return ErrorResponseModel(code=404, message="User not found", error={})

    user = user_mgmt.assign_role(db, user, role_id)
    if not user:
        return ErrorResponseModel(code=404, message="Role not found", error={})

    return ResponseModel(data=user_mgmt.serialize_user(user), message="Role assigned successfully")


@router.delete("/{user_id}/role", response_model=CommonResponse)
def remove_role(user_id: uuid.UUID, db: Session = Depends(get_db)):
    user = user_mgmt.get_user_by_id(db, user_id)
    if not user:
        return ErrorResponseModel(code=404, message="User not found", error={})

    user = user_mgmt.remove_role(db, user)
    return ResponseModel(data=user_mgmt.serialize_user(user), message="Role removed successfully")


# ── Tenants ────────────────────────────────────────────────────────────────────

@router.post("/{user_id}/tenants", response_model=CommonResponse)
def assign_tenants(user_id: uuid.UUID, tenant_ids: List[uuid.UUID], db: Session = Depends(get_db)):
    user = user_mgmt.get_user_by_id(db, user_id)
    if not user:
        return ErrorResponseModel(code=404, message="User not found", error={})

    result = user_mgmt.assign_tenants(db, user, tenant_ids)
    return ResponseModel(data=result, message="Tenants assigned successfully")


@router.delete("/{user_id}/tenants/{tenant_id}", response_model=CommonResponse)
def remove_tenant(user_id: uuid.UUID, tenant_id: uuid.UUID, db: Session = Depends(get_db)):
    removed = user_mgmt.remove_tenant(db, user_id, tenant_id)
    if not removed:
        return ErrorResponseModel(code=404, message="User-Tenant assignment not found", error={})
    return ResponseModel(data=None, message="Tenant removed from user")


@router.patch("/{user_id}/tenants/{tenant_id}/toggle", response_model=CommonResponse)
def toggle_user_tenant(user_id: uuid.UUID, tenant_id: uuid.UUID, db: Session = Depends(get_db)):
    ut = user_mgmt.toggle_user_tenant(db, user_id, tenant_id)
    if not ut:
        return ErrorResponseModel(code=404, message="User-Tenant assignment not found", error={})
    status = "activated" if ut.is_active else "deactivated"
    return ResponseModel(data=None, message=f"User-Tenant {status}")


# ── Districts ──────────────────────────────────────────────────────────────────

@router.post("/{user_id}/districts", response_model=CommonResponse)
def assign_districts(user_id: uuid.UUID, district_ids: List[uuid.UUID], db: Session = Depends(get_db)):
    user = user_mgmt.get_user_by_id(db, user_id)
    if not user:
        return ErrorResponseModel(code=404, message="User not found", error={})

    result = user_mgmt.assign_districts(db, user, district_ids)
    return ResponseModel(data=result, message="Districts assigned successfully")


@router.delete("/{user_id}/districts/{district_id}", response_model=CommonResponse)
def remove_district(user_id: uuid.UUID, district_id: uuid.UUID, db: Session = Depends(get_db)):
    removed = user_mgmt.remove_district(db, user_id, district_id)
    if not removed:
        return ErrorResponseModel(code=404, message="User-District assignment not found", error={})
    return ResponseModel(data=None, message="District removed from user")


@router.patch("/{user_id}/districts/{district_id}/toggle", response_model=CommonResponse)
def toggle_user_district(user_id: uuid.UUID, district_id: uuid.UUID, db: Session = Depends(get_db)):
    ud = user_mgmt.toggle_user_district(db, user_id, district_id)
    if not ud:
        return ErrorResponseModel(code=404, message="User-District assignment not found", error={})
    status = "activated" if ud.is_active else "deactivated"
    return ResponseModel(data=None, message=f"User-District {status}")


# ── Status / Admin actions ─────────────────────────────────────────────────────

@router.patch("/{user_id}/verify", response_model=CommonResponse)
def verify_user(user_id: uuid.UUID, db: Session = Depends(get_db)):
    user = user_mgmt.get_user_by_id(db, user_id)
    if not user:
        return ErrorResponseModel(code=404, message="User not found", error={})

    user_mgmt.verify_user(db, user)
    return ResponseModel(data=None, message="User verified successfully")


@router.patch("/{user_id}/toggle", response_model=CommonResponse)
def toggle_user(user_id: uuid.UUID, db: Session = Depends(get_db)):
    user = user_mgmt.get_user_by_id(db, user_id)
    if not user:
        return ErrorResponseModel(code=404, message="User not found", error={})

    user = user_mgmt.toggle_user_active(db, user)
    status = "activated" if user.is_active else "deactivated"
    return ResponseModel(data=None, message=f"User {status} successfully")


@router.patch("/{user_id}/reset-password", response_model=CommonResponse)
def reset_password(user_id: uuid.UUID, new_password: str, db: Session = Depends(get_db)):
    user = user_mgmt.get_user_by_id(db, user_id)
    if not user:
        return ErrorResponseModel(code=404, message="User not found", error={})

    user_mgmt.reset_password(db, user, new_password)
    return ResponseModel(data=None, message="Password reset successfully")