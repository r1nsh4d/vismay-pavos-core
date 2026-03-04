from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from sqlalchemy.orm import selectinload
from typing import List
import uuid

from app.models import User, UserTenant, UserDistrict, Tenant, District, Role, AuthToken, RolePermission
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.core.security import AuthMgmt


# ── User query with all relations eagerly loaded ───────────────────────────────

def _user_query():
    return select(User).options(
        selectinload(User.role).selectinload(Role.role_permissions).selectinload(RolePermission.permission),
        selectinload(User.user_tenants).selectinload(UserTenant.tenant),
        selectinload(User.user_districts).selectinload(UserDistrict.district),
    )


# ── Queries ────────────────────────────────────────────────────────────────────

async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(_user_query().where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_username_or_email(db: AsyncSession, username: str, email: str) -> User | None:
    result = await db.execute(
        select(User).where(
            (User.username == username) | (User.email == email)
        )
    )
    return result.scalar_one_or_none()


async def get_all_users(db, is_active=None, role_id=None, tenant_id=None, district_id=None, page=1, limit=20):
    query = select(User).options(
        selectinload(User.role).selectinload(Role.role_permissions).selectinload(RolePermission.permission),
        selectinload(User.user_tenants).selectinload(UserTenant.tenant),
        selectinload(User.user_districts).selectinload(UserDistrict.district),
    )

    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if role_id:
        query = query.where(User.role_id == role_id)
    if tenant_id:
        query = query.where(User.user_tenants.any(UserTenant.tenant_id == tenant_id))
    if district_id:
        query = query.where(User.user_districts.any(UserDistrict.district_id == district_id))

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar()

    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    return result.scalars().all(), total


# ── Create / Update / Delete ───────────────────────────────────────────────────

async def create_user(db: AsyncSession, user_in: UserCreate) -> User:
    user = User(
        username=user_in.username,
        first_name=user_in.first_name,
        last_name=user_in.last_name,
        email=user_in.email,
        phone=user_in.phone,
        password_hash=AuthMgmt.get_password_hash(user_in.password),
        role_id=user_in.role_id,
        profile_data=user_in.profile_data if hasattr(user_in, "profile_data") else None,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    await db.flush()

    await _seed_tenants(db, user.id, user_in.tenant_ids)
    await _seed_districts(db, user.id, user_in.district_ids)

    result = await db.execute(
        select(User)
        .options(
            selectinload(User.role)
            .selectinload(Role.role_permissions)
            .selectinload(RolePermission.permission),
            selectinload(User.user_tenants)
            .selectinload(UserTenant.tenant),
            selectinload(User.user_districts)
            .selectinload(UserDistrict.district),
        )
        .where(User.id == user.id)
    )
    return result.scalar_one()


async def update_user(db: AsyncSession, user: User, user_in: UserUpdate) -> User:
    if user_in.first_name is not None:
        user.first_name = user_in.first_name
    if user_in.last_name is not None:
        user.last_name = user_in.last_name
    if user_in.phone is not None:
        user.phone = user_in.phone
    if user_in.is_active is not None:
        user.is_active = user_in.is_active
    if hasattr(user_in, "profile_data") and user_in.profile_data is not None:
        merged = user.profile_data or {}
        merged.update(user_in.profile_data)
        user.profile_data = merged

    await db.flush()
    return user


async def delete_user(db: AsyncSession, user: User) -> None:
    await db.delete(user)
    await db.flush()


# ── Role ───────────────────────────────────────────────────────────────────────

async def assign_role(db: AsyncSession, user: User, role_id: uuid.UUID) -> User | None:
    result = await db.execute(select(Role).where(Role.id == role_id))
    if not result.scalar_one_or_none():
        return None
    user.role_id = role_id
    await db.flush()
    return user


async def remove_role(db: AsyncSession, user: User) -> User:
    user.role_id = None
    await db.flush()
    return user


# ── Tenants ────────────────────────────────────────────────────────────────────

async def assign_tenants(db: AsyncSession, user: User, tenant_ids: List[uuid.UUID]) -> dict:
    existing_ids = {ut.tenant_id for ut in user.user_tenants}
    added, not_found = [], []

    for tid in tenant_ids:
        if tid in existing_ids:
            continue
        result = await db.execute(
            select(Tenant).where(Tenant.id == tid, Tenant.is_active == True)
        )
        if not result.scalar_one_or_none():
            not_found.append(str(tid))
            continue
        db.add(UserTenant(user_id=user.id, tenant_id=tid))
        added.append(str(tid))

    await db.flush()
    return {"added": added, "notFound": not_found}


async def remove_tenant(db: AsyncSession, user_id: uuid.UUID, tenant_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(UserTenant).where(UserTenant.user_id == user_id, UserTenant.tenant_id == tenant_id)
    )
    ut = result.scalar_one_or_none()
    if not ut:
        return False
    await db.delete(ut)
    await db.flush()
    return True


async def toggle_user_tenant(db: AsyncSession, user_id: uuid.UUID, tenant_id: uuid.UUID) -> UserTenant | None:
    result = await db.execute(
        select(UserTenant).where(UserTenant.user_id == user_id, UserTenant.tenant_id == tenant_id)
    )
    ut = result.scalar_one_or_none()
    if not ut:
        return None
    ut.is_active = not ut.is_active
    await db.flush()
    return ut


# ── Districts ──────────────────────────────────────────────────────────────────

async def assign_districts(db: AsyncSession, user: User, district_ids: List[uuid.UUID]) -> dict:
    existing_ids = {ud.district_id for ud in user.user_districts}
    added, not_found = [], []

    for did in district_ids:
        if did in existing_ids:
            continue
        result = await db.execute(select(District).where(District.id == did))
        if not result.scalar_one_or_none():
            not_found.append(str(did))
            continue
        db.add(UserDistrict(user_id=user.id, district_id=did))
        added.append(str(did))

    await db.flush()
    return {"added": added, "notFound": not_found}


async def remove_district(db: AsyncSession, user_id: uuid.UUID, district_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(UserDistrict).where(UserDistrict.user_id == user_id, UserDistrict.district_id == district_id)
    )
    ud = result.scalar_one_or_none()
    if not ud:
        return False
    await db.delete(ud)
    await db.flush()
    return True


async def toggle_user_district(db: AsyncSession, user_id: uuid.UUID, district_id: uuid.UUID) -> UserDistrict | None:
    result = await db.execute(
        select(UserDistrict).where(UserDistrict.user_id == user_id, UserDistrict.district_id == district_id)
    )
    ud = result.scalar_one_or_none()
    if not ud:
        return None
    ud.is_active = not ud.is_active
    await db.flush()
    return ud


# ── Status helpers ─────────────────────────────────────────────────────────────

async def verify_user(db: AsyncSession, user: User) -> User:
    user.is_verified = True
    await db.flush()
    return user


async def toggle_user_active(db: AsyncSession, user: User) -> User:
    user.is_active = not user.is_active
    await db.flush()
    return user


async def reset_password(db: AsyncSession, user: User, new_password: str) -> User:
    user.password_hash = AuthMgmt.get_password_hash(new_password)
    result = await db.execute(
        select(AuthToken).where(AuthToken.user_id == user.id, AuthToken.is_active == True)
    )
    token_obj = result.scalar_one_or_none()
    if token_obj:
        token_obj.is_active = False
    await db.flush()
    return user


# ── Serialization ──────────────────────────────────────────────────────────────

def serialize_user(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        phone=user.phone,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        updated_at=user.updated_at,
        role_id=user.role_id,
        role_name=user.role.name if user.role else None,
        permissions=[
            rp.permission.code for rp in user.role.role_permissions if rp.permission
        ] if user.role else [],
        user_tenants=[
            {"tenantId": str(ut.tenant_id), "tenantName": ut.tenant.name,
             "tenantCode": ut.tenant.code, "isActive": ut.is_active}
            for ut in user.user_tenants if ut.tenant
        ],
        user_districts=[
            {"districtId": str(ud.district_id), "districtName": ud.district.name,
             "state": ud.district.state, "isActive": ud.is_active}
            for ud in user.user_districts if ud.district
        ],
        profile_data=user.profile_data if hasattr(user, "profile_data") else None,
    )


# ── Private helpers ────────────────────────────────────────────────────────────

async def _seed_tenants(db: AsyncSession, user_id: uuid.UUID, tenant_ids: List[uuid.UUID]) -> None:
    for tid in tenant_ids:
        result = await db.execute(
            select(Tenant).where(Tenant.id == tid, Tenant.is_active == True)
        )
        if result.scalar_one_or_none():
            db.add(UserTenant(user_id=user_id, tenant_id=tid))


async def _seed_districts(db: AsyncSession, user_id: uuid.UUID, district_ids: List[uuid.UUID]) -> None:
    for did in district_ids:
        result = await db.execute(select(District).where(District.id == did))
        if result.scalar_one_or_none():
            db.add(UserDistrict(user_id=user_id, district_id=did))