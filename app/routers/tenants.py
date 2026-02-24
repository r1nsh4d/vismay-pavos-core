from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.database import get_db
from app.dependencies import get_current_user
from app.models.tenant import Tenant
from app.schemas.common import ResponseModel
from app.schemas.tenant import TenantCreate, TenantResponse, TenantUpdate

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.get("")
async def list_tenants(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    offset = (page - 1) * page_size
    total = await db.scalar(select(func.count()).select_from(Tenant))
    result = await db.execute(select(Tenant).offset(offset).limit(page_size))
    tenants = [TenantResponse.model_validate(t).model_dump() for t in result.scalars().all()]
    return ResponseModel(
        data={"total": total, "page": page, "page_size": page_size, "results": tenants},
        message="Tenants fetched successfully",
    )


@router.post("", status_code=201)
async def create_tenant(
    payload: TenantCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    existing = await db.execute(select(Tenant).where(Tenant.code == payload.code))
    if existing.scalar_one_or_none():
        raise AppException(status_code=409, detail="Tenant code already exists", error_code="DUPLICATE_CODE")

    tenant = Tenant(**payload.model_dump())
    db.add(tenant)
    await db.flush()
    await db.refresh(tenant)
    return ResponseModel(
        data=TenantResponse.model_validate(tenant).model_dump(),
        message="Tenant created successfully",
    )


@router.get("/{tenant_id}")
async def get_tenant(tenant_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise AppException(status_code=404, detail="Tenant not found", error_code="NOT_FOUND")
    return ResponseModel(
        data=TenantResponse.model_validate(tenant).model_dump(),
        message="Tenant fetched successfully",
    )


@router.patch("/{tenant_id}")
async def update_tenant(
    tenant_id: int,
    payload: TenantUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise AppException(status_code=404, detail="Tenant not found", error_code="NOT_FOUND")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(tenant, field, value)
    await db.flush()
    await db.refresh(tenant)
    return ResponseModel(
        data=TenantResponse.model_validate(tenant).model_dump(),
        message="Tenant updated successfully",
    )


@router.delete("/{tenant_id}")
async def delete_tenant(tenant_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise AppException(status_code=404, detail="Tenant not found", error_code="NOT_FOUND")
    await db.delete(tenant)
    await db.flush()
    return ResponseModel(data=[], message="Tenant deleted successfully")
