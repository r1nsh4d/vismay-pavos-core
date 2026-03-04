from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List
import uuid

from app.models import Role, Permission, RolePermission
from app.schemas.role import RoleCreate


# ── Queries ────────────────────────────────────────────────────────────────────

async def get_role_by_id(db: AsyncSession, role_id: uuid.UUID) -> Role | None:
    result = await db.execute(
        select(Role)
        .options(selectinload(Role.role_permissions).selectinload(RolePermission.permission))
        .where(Role.id == role_id)
    )
    return result.scalar_one_or_none()


async def get_role_by_name(db: AsyncSession, name: str) -> Role | None:
    result = await db.execute(select(Role).where(Role.name == name))
    return result.scalar_one_or_none()


async def get_all_roles(
    db: AsyncSession,
    page: int = 1,
    limit: int = 20,
) -> tuple[List[Role], int]:
    query = select(Role).options(
        selectinload(Role.role_permissions).selectinload(RolePermission.permission)
    )

    total_result = await db.execute(select(func.count()).select_from(select(Role).subquery()))
    total = total_result.scalar()

    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    return result.scalars().all(), total


# ── Mutations ──────────────────────────────────────────────────────────────────

async def create_role(db: AsyncSession, role_in: RoleCreate) -> Role:
    role = Role(name=role_in.name, description=role_in.description)
    db.add(role)
    await db.flush()
    return role


async def update_role(db: AsyncSession, role: Role, role_in: RoleCreate) -> Role:
    role.name = role_in.name
    role.description = role_in.description
    await db.flush()
    return role


async def delete_role(db: AsyncSession, role: Role) -> None:
    await db.delete(role)
    await db.flush()


# ── Permission assignment ──────────────────────────────────────────────────────

async def assign_permissions_to_role(
    db: AsyncSession, role: Role, permission_ids: List[uuid.UUID]
) -> dict:
    # Fetch existing assigned permission IDs
    result = await db.execute(
        select(RolePermission.permission_id).where(RolePermission.role_id == role.id)
    )
    existing_ids = {row[0] for row in result.fetchall()}

    added, not_found = [], []
    for pid in permission_ids:
        if pid in existing_ids:
            continue
        perm = await db.execute(select(Permission).where(Permission.id == pid))
        if not perm.scalar_one_or_none():
            not_found.append(str(pid))
            continue
        db.add(RolePermission(role_id=role.id, permission_id=pid))
        added.append(str(pid))

    await db.flush()
    return {"added": added, "notFound": not_found}


async def remove_permission_from_role(
    db: AsyncSession, role_id: uuid.UUID, permission_id: uuid.UUID
) -> bool:
    result = await db.execute(
        select(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id,
        )
    )
    rp = result.scalar_one_or_none()
    if not rp:
        return False
    await db.delete(rp)
    await db.flush()
    return True


# ── Serializer ─────────────────────────────────────────────────────────────────

def serialize_role(role: Role) -> dict:
    return {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "permissionCodes": [
            rp.permission.code for rp in role.role_permissions if rp.permission
        ],
    }