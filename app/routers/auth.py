import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.database import get_db
from app.dependencies import get_current_user
from app.models import RolePermission, Role
from app.models.auth_token import AuthToken
from app.models.user import User, UserTenant, UserDistrict
from app.schemas.auth import LoginRequest, RefreshRequest
from app.schemas.common import ResponseModel
from app.schemas.user import UserResponse
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Auth"])


# ─── Helper ───────────────────────────────────────────────────────────────────

async def _get_user_with_relations(db: AsyncSession, user: User) -> dict:
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.role)
                .selectinload(Role.role_permissions)
                .selectinload(RolePermission.permission),
            selectinload(User.user_tenants).selectinload(UserTenant.tenant),
            selectinload(User.user_districts).selectinload(UserDistrict.district),
        )
        .where(User.id == user.id)
    )
    u = result.scalar_one()

    permissions = []
    if u.role and u.role.role_permissions:
        permissions = [rp.permission.code for rp in u.role.role_permissions if rp.permission]

    user_tenants = [
        {
            "id": str(ut.id),
            "tenant_id": str(ut.tenant_id),
            "is_active": ut.is_active,
            "name": ut.tenant.name,
            "code": ut.tenant.code,
        }
        for ut in u.user_tenants
    ]

    user_districts = [
        {
            "id": str(ud.id),
            "district_id": str(ud.district_id),
            "is_active": ud.is_active,
            "name": ud.district.name,
            "state": ud.district.state,
        }
        for ud in u.user_districts
    ]

    return {
        "id": str(u.id),
        "role_id": str(u.role_id) if u.role_id else None,
        "role": u.role.name if u.role else None,
        "permissions": permissions,
        "username": u.username,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "email": u.email,
        "phone": u.phone,
        "is_active": u.is_active,
        "is_verified": u.is_verified,
        "created_at": u.created_at,
        "updated_at": u.updated_at,
        "user_tenants": user_tenants,
        "user_districts": user_districts,
    }

# ─── Login ────────────────────────────────────────────────────────────────────

@router.post("/login")
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    # Support login with email OR username
    result = await db.execute(
        select(User).where(
            (User.email == payload.email) | (User.username == payload.email)
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password_hash):
        raise AppException(status_code=400, detail="Invalid credentials", error_code="INVALID_CREDENTIALS")

    if not user.is_active:
        raise AppException(status_code=403, detail="Account is inactive", error_code="ACCOUNT_INACTIVE")

    # 🔥 Critical: Cast UUIDs to string for JWT payload
    token_data = {
        "sub": str(user.id), 
        "role_id": str(user.role_id) if user.role_id else None
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    # AuthToken table now handles user_id as UUID
    db.add(AuthToken(
        user_id=user.id, 
        refresh_token=refresh_token, 
        expires_at=expires_at,
        is_revoked=False
    ))
    await db.flush()

    user_data = await _get_user_with_relations(db, user)

    return ResponseModel(
        data={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": user_data,
        },
        message="Login successful",
    )


# ─── Refresh ──────────────────────────────────────────────────────────────────

@router.post("/refresh")
async def refresh_token(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AuthToken).where(
            AuthToken.refresh_token == payload.refresh_token,
            AuthToken.is_revoked == False,
        )
    )
    db_token = result.scalar_one_or_none()

    if not db_token:
        raise AppException(status_code=401, detail="Invalid or revoked refresh token", error_code="INVALID_REFRESH_TOKEN")

    if db_token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise AppException(status_code=401, detail="Refresh token expired", error_code="REFRESH_TOKEN_EXPIRED")

    decoded = decode_token(payload.refresh_token)
    if not decoded or decoded.get("type") != "refresh":
        raise AppException(status_code=401, detail="Invalid refresh token", error_code="INVALID_REFRESH_TOKEN")

    # Generate new access token with the same UUID sub
    access_token = create_access_token({
        "sub": decoded["sub"],
        "role_id": decoded.get("role_id"),
    })

    return ResponseModel(
        data={"access_token": access_token, "token_type": "bearer"},
        message="Token refreshed successfully",
    )


# ─── Logout ───────────────────────────────────────────────────────────────────

@router.post("/logout")
async def logout(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AuthToken).where(AuthToken.refresh_token == payload.refresh_token)
    )
    db_token = result.scalar_one_or_none()

    if db_token:
        db_token.is_revoked = True
        await db.flush()

    return ResponseModel(data=[], message="Logged out successfully")


# ─── Me ───────────────────────────────────────────────────────────────────────

@router.get("/me")
async def me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # current_user is already fetched in dependencies.py using UUID
    user_data = await _get_user_with_relations(db, current_user)
    return ResponseModel(
        data=user_data,
        message="User profile fetched successfully",
    )