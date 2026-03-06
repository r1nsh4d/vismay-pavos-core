from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from uuid import UUID

from app.config import settings
from app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthMgmt:

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        return pwd_context.verify(plain, hashed)

    @staticmethod
    def get_password_hash(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def create_access_token(user_id: UUID) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        return jwt.encode(
            {"sub": str(user_id), "type": "access", "exp": expire},
            settings.SECRET_KEY, algorithm=settings.ALGORITHM,
        )

    @staticmethod
    def create_refresh_token(user_id: UUID) -> str:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        return jwt.encode(
            {"sub": str(user_id), "type": "refresh", "exp": expire},
            settings.SECRET_KEY, algorithm=settings.ALGORITHM,
        )

    @staticmethod
    async def store_refresh_token(db: AsyncSession, user_id: UUID, refresh_token: str):
        from app.models import AuthToken

        result = await db.execute(
            select(AuthToken).where(AuthToken.user_id == user_id)
        )
        existing = result.scalar_one_or_none()

        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        if existing:
            # Update in place — no new row, no unique violation
            existing.refresh_token = refresh_token
            existing.is_active = True
            existing.expires_at = expires_at
        else:
            db.add(AuthToken(
                user_id=user_id,
                refresh_token=refresh_token,
                is_active=True,
                expires_at=expires_at,
            ))

    @staticmethod
    async def validate_refresh_token(db: AsyncSession, refresh_token: str) -> UUID | None:
        from app.models import AuthToken
        try:
            result = await db.execute(
                select(AuthToken).where(
                    AuthToken.refresh_token == refresh_token,
                    AuthToken.is_active == True,
                    AuthToken.expires_at > datetime.now(timezone.utc),
                )
            )
            token_obj = result.scalar_one_or_none()
            if not token_obj:
                return None
            payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            if payload.get("type") != "refresh":
                return None
            return UUID(payload["sub"])
        except (JWTError, KeyError, ValueError):
            return None

    @staticmethod
    async def validate_access_token(db: AsyncSession, token: str) -> UUID | None:
        from app.models import User
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            if payload.get("type") != "access":
                return None
            user_id = payload.get("sub")
            if not user_id:
                return None
            result = await db.execute(
                select(User).where(User.id == UUID(user_id), User.is_active == True)
            )
            user = result.scalar_one_or_none()
            if not user:
                return None
            return UUID(user_id)
        except (JWTError, KeyError, ValueError):
            return None

    @staticmethod
    async def authenticate_user(db: AsyncSession, login: str, password: str):
        result = await db.execute(
            select(User).where(or_(User.username == login, User.email == login))
        )
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            return None
        if not AuthMgmt.verify_password(password, user.password_hash):
            return None
        return user