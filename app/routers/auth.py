from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.database import get_db
from app.dependencies import get_current_user
from app.models.auth_token import AuthToken
from app.models.user import User
from app.schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
)
from app.schemas.common import ResponseModel, ErrorResponseModel
from app.schemas.user import UserResponse
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login")
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password_hash):
        raise AppException(status_code=401, detail="Invalid email or password", error_code="INVALID_CREDENTIALS")

    if not user.is_active:
        raise AppException(status_code=403, detail="Account is inactive", error_code="ACCOUNT_INACTIVE")

    token_data = {"sub": str(user.id), "tenant_id": str(user.tenant_id)}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db_token = AuthToken(user_id=user.id, refresh_token=refresh_token, expires_at=expires_at)
    db.add(db_token)
    await db.flush()

    return ResponseModel(
        data={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
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

    access_token = create_access_token({"sub": decoded["sub"], "tenant_id": decoded.get("tenant_id")})
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
async def me(current_user: User = Depends(get_current_user)):
    return ResponseModel(
        data=UserResponse.model_validate(current_user).model_dump(),
        message="User profile fetched successfully",
    )
