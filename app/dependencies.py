from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.security import AuthMgmt
from app.models import User, Role, RolePermission

# Roles that may only ever READ — any write (POST/PUT/PATCH/DELETE) is rejected.
READ_ONLY_ROLES = {"viewer"}
_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = await AuthMgmt.validate_access_token(db, credentials.credentials)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(
        select(User)
        .options(
            selectinload(User.role).selectinload(Role.role_permissions).selectinload(RolePermission.permission)
        )
        .where(User.id == user_id, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_roles(*roles: str):
    async def checker(current_user: User = Depends(get_current_user)) -> User:
        if not current_user.role or current_user.role.name not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(roles)}",
            )
        return current_user
    return checker


async def block_read_only_writes(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> User:
    """Router-level guard: a read-only role (e.g. viewer) may GET anything on this router
    but is rejected on any write method. All other roles are unaffected. Add this to the
    routers a viewer can reach that also have write endpoints."""
    if (
        request.method in _WRITE_METHODS
        and current_user.role
        and current_user.role.name in READ_ONLY_ROLES
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This is a read-only account.",
        )
    return current_user


def restrict_read_only_to(*allowed_substrings: str):
    """Router-level guard factory: a read-only role (e.g. viewer) may only reach request
    paths containing one of `allowed_substrings`; everything else on the router is 403.
    Other roles are unaffected. Used to limit the viewer to the order report only."""
    async def checker(
        request: Request,
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role and current_user.role.name in READ_ONLY_ROLES:
            path = request.url.path
            if not any(sub in path for sub in allowed_substrings):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This account can only access the order report.",
                )
        return current_user
    return checker


def require_permissions(*permissions: str):
    async def checker(current_user: User = Depends(get_current_user)) -> User:
        if not current_user.role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No role assigned")
        user_permissions = {
            rp.permission.code
            for rp in current_user.role.role_permissions
            if rp.permission
        }
        missing = set(permissions) - user_permissions
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permissions: {', '.join(missing)}",
            )
        return current_user
    return checker