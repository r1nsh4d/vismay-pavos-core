import datetime
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import User, AuthToken
from app.schemas.auth import LoginRequest


class AuthMgmt:

    @staticmethod
    async def fetch_user_by_email_or_username(db: AsyncSession, payload: LoginRequest):
        # Support login with email OR username
        result = await db.execute(
            select(User).where(
                (User.email == payload.email) | (User.username == payload.email)
            )
        )
        user = result.scalar_one_or_none()
        if not user:
            return None
        return user

    @staticmethod
    async def update_refresh_token(
            db: AsyncSession,
            user_id: uuid.UUID,
            new_refresh_token: str,
            new_expires_at: datetime,
    ) -> None:
        # Revoke existing active token
        result = await db.execute(
            select(AuthToken)
            .where(AuthToken.user_id == user_id, AuthToken.is_revoked == False)
            .order_by(AuthToken.created_at.desc())
            .limit(1)
        )
        existing_token = result.scalar_one_or_none()

        if existing_token:
            existing_token.is_revoked = True
            await db.flush()

        # Insert new token
        new_token = AuthToken(
            user_id=user_id,
            refresh_token=new_refresh_token,
            expires_at=new_expires_at,
            is_revoked=False,
        )
        db.add(new_token)
        await db.flush()

    @staticmethod
    async def get_active_refresh_token(db: AsyncSession, refresh_token: str) -> AuthToken | None:
        result = await db.execute(
            select(AuthToken).where(
                AuthToken.refresh_token == refresh_token,
                AuthToken.is_revoked == False,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def revoke_refresh_token(db: AsyncSession, refresh_token: str) -> bool:
        result = await db.execute(
            update(AuthToken)
            .where(AuthToken.refresh_token == refresh_token)
            .values(is_revoked=True)
        )
        await db.flush()
        return result.rowcount > 0
