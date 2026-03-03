import asyncio
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
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
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest
from app.schemas.common import ResponseModel
from app.config import settings
from app.services.auth import AuthMgmt
from app.services.users import UserMgmt

router = APIRouter(prefix="/auth", tags=["Auth"])


# ─── Login ────────────────────────────────────────────────────────────────────

@router.post("/login")
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await AuthMgmt.fetch_user_by_email_or_username(db, payload)

    if not user or not verify_password(payload.password, user.password_hash):
        raise AppException(
            status_code=400,
            detail="Invalid credentials",
            error_code="INVALID_CREDENTIALS"
        )

    if not user.is_active:
        raise AppException(
            status_code=403,
            detail="Account is inactive",
            error_code="ACCOUNT_INACTIVE"
        )

    token_data = {
        "sub": str(user.id),
        "role_id": str(user.role_id) if user.role_id else None,
    }

    access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)).isoformat()

    user_data, _ = await asyncio.gather(
        UserMgmt.get_user_with_relations(db, user),
        AuthMgmt.update_refresh_token(
            db=db,
            user_id=user.id,
            new_refresh_token=new_refresh_token,
            new_expires_at=expires_at,
        ),
    )

    await db.commit()

    return ResponseModel(
        data={
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "user": user_data,
        },
        message="Login successful",
    )


# ─── Refresh ──────────────────────────────────────────────────────────────────

@router.post("/refresh")
async def refresh_token(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    decoded = decode_token(payload.refresh_token)
    if not decoded or decoded.get("type") != "refresh":
        raise AppException(
            status_code=401,
            detail="Invalid refresh token",
            error_code="INVALID_REFRESH_TOKEN"
        )

    db_token = await AuthMgmt.get_active_refresh_token(db, payload.refresh_token)
    if not db_token:
        raise AppException(
            status_code=401,
            detail="Invalid or revoked refresh token",
            error_code="INVALID_REFRESH_TOKEN"
        )

    if db_token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise AppException(
            status_code=401,
            detail="Refresh token expired",
            error_code="REFRESH_TOKEN_EXPIRED"
        )

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
    revoked = await AuthMgmt.revoke_refresh_token(db, payload.refresh_token)

    if not revoked:
        raise AppException(
            status_code=401,
            detail="Invalid refresh token",
            error_code="INVALID_REFRESH_TOKEN"
        )

    await db.commit()
    return ResponseModel(data=[], message="Logged out successfully")


# ─── Me ───────────────────────────────────────────────────────────────────────

@router.get("/me")
async def me(
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    user_data = await UserMgmt.get_user_with_relations(db, current_user)
    return ResponseModel(
        data=user_data,
        message="User profile fetched successfully",
    )