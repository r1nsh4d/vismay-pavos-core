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


async def _get_user_with_relations(db: AsyncSession, user: User) -> User:
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.role)
                .selectinload(Role.role_permissions)
                .selectinload(RolePermission.permission),  # ← this was missing
            selectinload(User.user_tenants).selectinload(UserTenant.tenant),
            selectinload(User.user_districts).selectinload(UserDistrict.district),
        )
        .where(User.id == user.id)
    )
    return result.scalar_one()



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
        raise AppException(status_code=401, detail="Invalid credentials", error_code="INVALID_CREDENTIALS")

    if not user.is_active:
        raise AppException(status_code=403, detail="Account is inactive", error_code="ACCOUNT_INACTIVE")

    # token_data no longer has tenant_id since user can have multiple tenants
    token_data = {"sub": str(user.id), "role_id": str(user.role_id)}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db.add(AuthToken(user_id=user.id, refresh_token=refresh_token, expires_at=expires_at))
    await db.flush()

    user = await _get_user_with_relations(db, user)

    return ResponseModel(
        data={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": UserResponse.model_validate(user).model_dump(),
        },
        message="Login successful",
    )


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

    access_token = create_access_token({
        "sub": decoded["sub"],
        "role_id": decoded.get("role_id"),
    })

    return ResponseModel(
        data={"access_token": access_token, "token_type": "bearer"},
        message="Token refreshed successfully",
    )


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


@router.get("/me")
async def me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = await _get_user_with_relations(db, current_user)
    return ResponseModel(
        data=UserResponse.model_validate(user).model_dump(),
        message="User profile fetched successfully",
    )