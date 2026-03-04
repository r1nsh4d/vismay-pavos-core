from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid

from app.models import Tenant
from app.schemas.tenant import TenantCreate


async def get_tenant_by_id(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant | None:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none()


async def get_tenant_by_code(db: AsyncSession, code: str) -> Tenant | None:
    result = await db.execute(select(Tenant).where(Tenant.code == code))
    return result.scalar_one_or_none()


async def get_all_tenants(db: AsyncSession, is_active: bool | None = None) -> List[Tenant]:
    query = select(Tenant)
    if is_active is not None:
        query = query.where(Tenant.is_active == is_active)
    result = await db.execute(query)
    return result.scalars().all()


async def create_tenant(db: AsyncSession, tenant_in: TenantCreate) -> Tenant:
    tenant = Tenant(name=tenant_in.name, code=tenant_in.code)
    db.add(tenant)
    await db.flush()
    return tenant


async def update_tenant(db: AsyncSession, tenant: Tenant, tenant_in: TenantCreate) -> Tenant:
    tenant.name = tenant_in.name
    tenant.code = tenant_in.code
    await db.flush()
    return tenant


async def toggle_tenant_active(db: AsyncSession, tenant: Tenant) -> Tenant:
    tenant.is_active = not tenant.is_active
    await db.flush()
    return tenant


async def delete_tenant(db: AsyncSession, tenant: Tenant) -> None:
    await db.delete(tenant)
    await db.flush()