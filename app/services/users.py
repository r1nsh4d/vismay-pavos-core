from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import User, Role, RolePermission
from app.models.user import UserTenant, UserDistrict


class UserMgmt:

    @staticmethod
    async def get_user_with_relations(db: AsyncSession, user: User) -> dict:
        result = await db.execute(
            select(User)
            .options(
                selectinload(User.role)
                    .selectinload(Role.role_permissions)
                    .selectinload(RolePermission.permission),
                selectinload(User.user_tenants).selectinload(UserTenant.tenant),
                selectinload(User.user_districts).selectinload(UserDistrict.district),
            )
            .where(User.id == user.id)
        )
        u = result.scalar_one()

        permissions = []
        if u.role and u.role.role_permissions:
            permissions = [rp.permission.code for rp in u.role.role_permissions if rp.permission]

        user_tenants = [
            {
                "id": str(ut.id),
                "tenant_id": str(ut.tenant_id),
                "is_active": ut.is_active,
                "name": ut.tenant.name,
                "code": ut.tenant.code,
            }
            for ut in u.user_tenants
        ]

        user_districts = [
            {
                "id": str(ud.id),
                "district_id": str(ud.district_id),
                "is_active": ud.is_active,
                "name": ud.district.name,
                "state": ud.district.state,
            }
            for ud in u.user_districts
        ]

        return {
            "id": str(u.id),
            "role_id": str(u.role_id) if u.role_id else None,
            "role": u.role.name if u.role else None,
            "permissions": permissions,
            "username": u.username,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "email": u.email,
            "phone": u.phone,
            "is_active": u.is_active,
            "is_verified": u.is_verified,
            "created_at": u.created_at,
            "updated_at": u.updated_at,
            "user_tenants": user_tenants,
            "user_districts": user_districts,
        }
