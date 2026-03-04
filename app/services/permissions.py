from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid

from app.models import Permission
from app.schemas.permission import PermissionCreate


async def get_permission_by_id(db: AsyncSession, permission_id: uuid.UUID) -> Permission | None:
    result = await db.execute(select(Permission).where(Permission.id == permission_id))
    return result.scalar_one_or_none()


async def get_permission_by_code(db: AsyncSession, code: str) -> Permission | None:
    result = await db.execute(select(Permission).where(Permission.code == code))
    return result.scalar_one_or_none()


async def get_all_permissions(db: AsyncSession) -> List[Permission]:
    result = await db.execute(select(Permission))
    return result.scalars().all()


async def create_permission(db: AsyncSession, perm_in: PermissionCreate) -> Permission:
    perm = Permission(name=perm_in.name, code=perm_in.code, description=perm_in.description)
    db.add(perm)
    await db.flush()
    return perm


async def update_permission(db: AsyncSession, perm: Permission, perm_in: PermissionCreate) -> Permission:
    perm.name = perm_in.name
    perm.code = perm_in.code
    perm.description = perm_in.description
    await db.flush()
    return perm


async def delete_permission(db: AsyncSession, perm: Permission) -> None:
    await db.delete(perm)
    await db.flush()