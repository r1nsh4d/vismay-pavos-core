import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.database import get_db
from app.dependencies import get_current_user
from app.models.tenant import Tenant
from app.schemas.common import ResponseModel, PaginatedResponse
from app.schemas.tenant import TenantCreate, TenantResponse, TenantUpdate

router = APIRouter(prefix="/tenants", tags=["Tenants"])


# ─── List All ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_tenants(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    is_active: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    offset = (page - 1) * limit
    query = select(Tenant)
    count_query = select(func.count()).select_from(Tenant)

    if is_active is not None:
        query = query.where(Tenant.is_active == is_active)
        count_query = count_query.where(Tenant.is_active == is_active)

    total = await db.scalar(count_query) or 0
    result = await db.execute(query.offset(offset).limit(limit))
    tenants = [TenantResponse.model_validate(t).model_dump() for t in result.scalars().all()]

    return PaginatedResponse(
        data=tenants,
        message="Tenants fetched successfully",
        limit=limit,
        page=page,
        total=total
    )


# ─── Get by ID ────────────────────────────────────────────────────────────────

@router.get("/{tenant_id}")
async def get_tenant(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if not tenant:
        raise AppException(status_code=404, detail="Tenant not found", error_code="NOT_FOUND")

    return ResponseModel(
        data=TenantResponse.model_validate(tenant).model_dump(),
        message="Tenant fetched successfully",
    )


# ─── Create ───────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_tenant(
    payload: TenantCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    existing = await db.scalar(select(Tenant).where(Tenant.code == payload.code))
    if existing:
        raise AppException(status_code=409, detail="Tenant code already exists", error_code="DUPLICATE_CODE")

    tenant = Tenant(**payload.model_dump())
    db.add(tenant)
    await db.flush()
    await db.refresh(tenant)

    return ResponseModel(
        data=TenantResponse.model_validate(tenant).model_dump(),
        message="Tenant created successfully",
    )


# ─── Update ───────────────────────────────────────────────────────────────────

@router.patch("/{tenant_id}")
async def update_tenant(
    tenant_id: uuid.UUID,
    payload: TenantUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if not tenant:
        raise AppException(status_code=404, detail="Tenant not found", error_code="NOT_FOUND")

    # Check duplicate code if code is being changed
    if payload.code and payload.code != tenant.code:
        duplicate = await db.scalar(
            select(Tenant).where(Tenant.code == payload.code, Tenant.id != tenant_id)
        )
        if duplicate:
            raise AppException(status_code=409, detail="Tenant code already exists", error_code="DUPLICATE_CODE")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(tenant, field, value)

    await db.flush()
    await db.refresh(tenant)

    return ResponseModel(
        data=TenantResponse.model_validate(tenant).model_dump(),
        message="Tenant updated successfully",
    )


# ─── Activate ─────────────────────────────────────────────────────────────────

@router.patch("/{tenant_id}/activate")
async def activate_tenant(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if not tenant:
        raise AppException(status_code=404, detail="Tenant not found", error_code="NOT_FOUND")
    
    tenant.is_active = True
    await db.flush()

    return ResponseModel(
        data={"id": tenant_id, "is_active": True}, 
        message="Tenant activated successfully"
    )


# ─── Deactivate ───────────────────────────────────────────────────────────────

@router.patch("/{tenant_id}/deactivate")
async def deactivate_tenant(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if not tenant:
        raise AppException(status_code=404, detail="Tenant not found", error_code="NOT_FOUND")
    
    tenant.is_active = False
    await db.flush()

    return ResponseModel(
        data={"id": tenant_id, "is_active": False}, 
        message="Tenant deactivated successfully"
    )


# ─── Delete ───────────────────────────────────────────────────────────────────

@router.delete("/{tenant_id}")
async def delete_tenant(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if not tenant:
        raise AppException(status_code=404, detail="Tenant not found", error_code="NOT_FOUND")

    await db.delete(tenant)
    await db.flush()

    return ResponseModel(data=[], message="Tenant deleted successfully")