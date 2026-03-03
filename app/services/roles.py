import asyncio

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.models import Permission
from app.schemas.permission import PermissionResponse, PermissionCreate


class RoleMgmt:

    @staticmethod
    async def get_permissions_paginated(db: AsyncSession, page: int, limit: int) -> tuple[list, int]:
        offset = (page - 1) * limit
        total, result = await asyncio.gather(
            db.scalar(select(func.count()).select_from(Permission)),
            db.execute(select(Permission).offset(offset).limit(limit)),
        )
        perms = [PermissionResponse.model_validate(p).model_dump() for p in result.scalars().all()]
        return perms, total or 0

    @staticmethod
    async def get_permission_by_id(db: AsyncSession, permission_id: str):
        perm = await db.scalar(select(Permission).where(Permission.id == permission_id))
        if not perm:
            return None
        return perm

    @staticmethod
    async def create_permission(db: AsyncSession, payload: PermissionCreate) -> Permission:
        code_exists, name_exists = await asyncio.gather(
            db.scalar(select(Permission.id).where(Permission.code == payload.code)),
            db.scalar(select(Permission.id).where(Permission.name == payload.name)),
        )

        if code_exists:
            raise AppException(status_code=409, detail="Permission code already exists", error_code="DUPLICATE_CODE")

        if name_exists:
            raise AppException(status_code=409, detail="Permission name already exists", error_code="DUPLICATE_NAME")

        perm = Permission(**payload.model_dump())
        db.add(perm)
        await db.flush()
        await db.refresh(perm)
        return perm

    