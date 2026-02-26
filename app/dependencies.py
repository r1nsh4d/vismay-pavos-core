from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.security import decode_token
from app.database import get_db

security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from app.models.user import User

    token = credentials.credentials
    payload = decode_token(token)

    if not payload or payload.get("type") != "access":
        raise AppException(status_code=401, detail="Invalid or expired token", error_code="INVALID_TOKEN")

    user_id = payload.get("sub")
    if not user_id:
        raise AppException(status_code=401, detail="Invalid token payload", error_code="INVALID_TOKEN")

    result = await db.execute(select(User).where(User.id == int(user_id), User.is_active == True))
    user = result.scalar_one_or_none()

    if not user:
        raise AppException(status_code=401, detail="User not found or inactive", error_code="USER_NOT_FOUND")

    return user


def require_roles(*allowed_roles: str):
    """Dependency factory that checks user role name."""
    async def _check(current_user=Depends(get_current_user)):
        from app.models.role import Role
        role_name = None
        if current_user.role:
            role_name = current_user.role.name
        if role_name not in allowed_roles:
            raise AppException(
                status_code=403,
                detail=f"Access denied. Required roles: {', '.join(allowed_roles)}",
                error_code="FORBIDDEN",
            )
        return current_user
    return _check


CurrentUser = Annotated[any, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
