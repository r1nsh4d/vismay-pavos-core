from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func, delete
from sqlalchemy.orm import selectinload
from typing import List, Tuple
import uuid

from app.core.exceptions import AppException
from app.models import (
    User, UserTenant, UserDistrict, Tenant,
    District, Role, AuthToken, RolePermission,
)
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.core.security import AuthMgmt


# ── Query helper ───────────────────────────────────────────────────────────────

def _user_query():
    return select(User).options(
        selectinload(User.role)
            .selectinload(Role.role_permissions)
            .selectinload(RolePermission.permission),
        selectinload(User.user_tenants)
            .selectinload(UserTenant.tenant),
        selectinload(User.user_districts)
            .selectinload(UserDistrict.district)
            .selectinload(District.state),   # ← loads state for district
    )


async def hydrate_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    result = await db.execute(_user_query().where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError(f"User {user_id} not found during hydration")
    return user


# ── Queries ────────────────────────────────────────────────────────────────────

async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(_user_query().where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_username_or_email(db: AsyncSession, username: str, email: str) -> User | None:
    result = await db.execute(
        _user_query().where(
            (User.username == username) | (User.email == email)
        )
    )
    return result.scalar_one_or_none()


async def get_all_users(
    db: AsyncSession,
    is_active=None, role_id=None, tenant_id=None,
    district_id=None, page=1, limit=20,
) -> Tuple[List[User], int]:
    query = _user_query()

    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if role_id:
        query = query.where(User.role_id == role_id)
    if tenant_id:
        query = query.where(User.user_tenants.any(UserTenant.tenant_id == tenant_id))
    if district_id:
        query = query.where(User.user_districts.any(UserDistrict.district_id == district_id))

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar() or 0

    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    return result.scalars().unique().all(), total


async def search_users(
    db: AsyncSession,
    q: str | None = None,
    tenant_ids: List[uuid.UUID] = [],
    district_ids: List[uuid.UUID] = [],
    role_ids: List[uuid.UUID] = [],
    is_active: bool | None = None,
    page: int = 1,
    limit: int = 20,
) -> Tuple[List[User], int]:
    query = _user_query()

    if q:
        query = query.where(
            or_(User.username.ilike(f"%{q}%"), User.email.ilike(f"%{q}%"))
        )
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if role_ids:
        query = query.where(User.role_id.in_(role_ids))
    if tenant_ids:
        query = query.where(User.user_tenants.any(UserTenant.tenant_id.in_(tenant_ids)))
    if district_ids:
        query = query.where(User.user_districts.any(UserDistrict.district_id.in_(district_ids)))

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar() or 0

    result = await db.execute(query.offset((page - 1) * limit).limit(limit))
    return result.scalars().unique().all(), total


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
        profile_data=user_in.profile_data,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    await db.flush()

    await _seed_tenants(db, user.id, user_in.tenant_ids)
    await _seed_districts(db, user.id, user_in.district_ids)

    return await hydrate_user(db, user.id)


async def update_user(db: AsyncSession, user: User, user_in: UserUpdate) -> User:
    if user_in.first_name is not None:
        user.first_name = user_in.first_name
    if user_in.last_name is not None:
        user.last_name = user_in.last_name
    if user_in.phone is not None:
        user.phone = user_in.phone
    if user_in.is_active is not None:
        user.is_active = user_in.is_active
    if user_in.profile_data is not None:
        merged = (user.profile_data or {}).copy()
        merged.update(user_in.profile_data)
        user.profile_data = merged

    await db.flush()
    return await hydrate_user(db, user.id)


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
    return await hydrate_user(db, user.id)


async def remove_role(db: AsyncSession, user: User) -> User:
    user.role_id = None
    await db.flush()
    return await hydrate_user(db, user.id)


# ── Tenants ────────────────────────────────────────────────────────────────────

async def assign_tenants(db: AsyncSession, user: User, tenant_ids: List[uuid.UUID]) -> User:
    res = await db.execute(select(UserTenant.tenant_id).where(UserTenant.user_id == user.id))
    existing_ids = set(res.scalars().all())

    for tid in tenant_ids:
        if tid in existing_ids:
            continue
        result = await db.execute(
            select(Tenant).where(Tenant.id == tid, Tenant.is_active == True)
        )
        if result.scalar_one_or_none():
            db.add(UserTenant(user_id=user.id, tenant_id=tid))

    await db.flush()
    return await hydrate_user(db, user.id)


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

async def assign_districts(db: AsyncSession, user: User, district_ids: List[uuid.UUID]) -> User:
    res = await db.execute(select(UserDistrict.district_id).where(UserDistrict.user_id == user.id))
    existing_ids = set(res.scalars().all())

    for did in district_ids:
        if did in existing_ids:
            continue
        result = await db.execute(select(District).where(District.id == did))
        if result.scalar_one_or_none():
            db.add(UserDistrict(user_id=user.id, district_id=did))

    await db.flush()
    return await hydrate_user(db, user.id)


async def remove_districts(db: AsyncSession, user_id: uuid.UUID, district_ids: List[uuid.UUID]) -> User:
    await db.execute(
        delete(UserDistrict).where(
            UserDistrict.user_id == user_id,
            UserDistrict.district_id.in_(district_ids),
        )
    )
    await db.flush()
    return await hydrate_user(db, user_id)


async def toggle_user_district(db: AsyncSession, user_id: uuid.UUID, district_id: uuid.UUID) -> UserDistrict:
    result = await db.execute(
        select(UserDistrict).where(
            UserDistrict.user_id == user_id,
            UserDistrict.district_id == district_id,
        )
    )
    ud = result.scalar_one_or_none()
    if not ud:
        raise AppException(status_code=404, detail="District not assigned to user")
    ud.is_active = not ud.is_active
    await db.flush()
    return ud


# ── Status helpers ─────────────────────────────────────────────────────────────

async def verify_user(db: AsyncSession, user: User) -> User:
    user.is_verified = True
    await db.flush()
    return await hydrate_user(db, user.id)


async def toggle_user_active(db: AsyncSession, user: User) -> User:
    user.is_active = not user.is_active
    await db.flush()
    return await hydrate_user(db, user.id)


async def reset_password(db: AsyncSession, user: User, new_password: str) -> User:
    user.password_hash = AuthMgmt.get_password_hash(new_password)
    result = await db.execute(
        select(AuthToken).where(AuthToken.user_id == user.id, AuthToken.is_active == True)
    )
    token_obj = result.scalar_one_or_none()
    if token_obj:
        token_obj.is_active = False
    await db.flush()
    return await hydrate_user(db, user.id)


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
            rp.permission.code
            for rp in (user.role.role_permissions if user.role else [])
            if rp.permission
        ],
        user_tenants=[
            {
                "tenantId": str(ut.tenant_id),
                "tenantName": ut.tenant.name if ut.tenant else "Unknown",
                "tenantCode": ut.tenant.code if ut.tenant else "N/A",
                "isActive": ut.is_active,
            }
            for ut in (user.user_tenants or [])
        ],
        user_districts=[
            {
                "districtId": str(ud.district_id),
                "districtName": ud.district.name if ud.district else "Unknown",
                "stateName": ud.district.state.name if ud.district and ud.district.state else None,
                "stateCode": ud.district.state.code if ud.district and ud.district.state else None,
                "isActive": ud.is_active,
            }
            for ud in (user.user_districts or [])
        ],
        profile_data=user.profile_data,
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