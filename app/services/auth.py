from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from uuid import UUID

from app.core.security import AuthMgmt
from app.models import User, AuthToken, UserTenant, UserDistrict, Tenant, District
from app.schemas.user import UserCreate


async def get_user_by_username_or_email(db: AsyncSession, username: str, email: str) -> User | None:
    result = await db.execute(
        select(User).where(or_(User.username == username, User.email == email))
    )
    return result.scalar_one_or_none()


async def create_user_record(db: AsyncSession, user_in: UserCreate) -> User:
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

    for tenant_id in user_in.tenant_ids:
        result = await db.execute(
            select(Tenant).where(Tenant.id == tenant_id, Tenant.is_active == True)
        )
        if result.scalar_one_or_none():
            db.add(UserTenant(user_id=user.id, tenant_id=tenant_id))

    for district_id in user_in.district_ids:
        result = await db.execute(select(District).where(District.id == district_id))
        if result.scalar_one_or_none():
            db.add(UserDistrict(user_id=user.id, district_id=district_id))

    return user


async def authenticate(db: AsyncSession, login: str, password: str) -> User | None:
    return await AuthMgmt.authenticate_user(db, login=login, password=password)


async def issue_token_pair(db: AsyncSession, user_id: UUID) -> dict:
    access = AuthMgmt.create_access_token(user_id=user_id)
    refresh = AuthMgmt.create_refresh_token(user_id=user_id)
    await AuthMgmt.store_refresh_token(db=db, user_id=user_id, refresh_token=refresh)
    return {"accessToken": access, "refreshToken": refresh, "tokenType": "bearer"}


async def validate_refresh(db: AsyncSession, refresh_token: str) -> UUID | None:
    return await AuthMgmt.validate_refresh_token(db, refresh_token)


async def revoke_refresh_token(db: AsyncSession, user_id: UUID) -> bool:
    result = await db.execute(
        select(AuthToken).where(AuthToken.user_id == user_id, AuthToken.is_active == True)
    )
    token_obj = result.scalar_one_or_none()
    if not token_obj:
        return False
    token_obj.is_active = False
    return True