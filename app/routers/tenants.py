from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.core.exceptions import AppException
from app.database import get_db
from app.dependencies import get_current_user, require_roles, require_permissions
from app.schemas.common import CommonResponse, ErrorResponseModel, ResponseModel, PaginatedResponse
from app.schemas.tenant import TenantCreate, TenantResponse
from app.services import tenants as tenant_mgmt

router = APIRouter(
    prefix="/tenants", tags=["Tenants"], dependencies=[Depends(require_roles("super_admin", "admin"))])


@router.post("", response_model=CommonResponse)
async def create_tenant(tenant_in: TenantCreate, db: AsyncSession = Depends(get_db)):
    if await tenant_mgmt.get_tenant_by_code(db, tenant_in.code):
        raise AppException(status_code=400, detail="Tenant code already exists")

    tenant = await tenant_mgmt.create_tenant(db, tenant_in)
    return ResponseModel(data=TenantResponse.model_validate(tenant), message="Tenant created")


@router.get("", response_model=CommonResponse)
async def list_tenants(
    is_active: bool | None = None,
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    tenants, total = await tenant_mgmt.get_all_tenants(db, is_active=is_active, page=page, limit=limit)
    return PaginatedResponse(
        data=[TenantResponse.model_validate(t) for t in tenants],
        message="Tenants fetched",
        page=page,
        limit=limit,
        total=total,
    )


@router.get("/{tenant_id}", response_model=CommonResponse)
async def get_tenant(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    tenant = await tenant_mgmt.get_tenant_by_id(db, tenant_id)
    if not tenant:
        raise AppException(status_code=404, detail="Tenant not found")
    return ResponseModel(data=TenantResponse.model_validate(tenant), message="Tenant fetched")


@router.put("/{tenant_id}", response_model=CommonResponse)
async def update_tenant(tenant_id: uuid.UUID, tenant_in: TenantCreate, db: AsyncSession = Depends(get_db)):
    tenant = await tenant_mgmt.get_tenant_by_id(db, tenant_id)
    if not tenant:
        raise AppException(status_code=404, detail="Tenant not found")

    conflict = await tenant_mgmt.get_tenant_by_code(db, tenant_in.code)
    if conflict and conflict.id != tenant_id:
        raise AppException(status_code=400, detail="Tenant code already in use")

    tenant = await tenant_mgmt.update_tenant(db, tenant, tenant_in)
    return ResponseModel(data=TenantResponse.model_validate(tenant), message="Tenant updated")


@router.patch("/{tenant_id}/toggle", response_model=CommonResponse)
async def toggle_tenant(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    tenant = await tenant_mgmt.get_tenant_by_id(db, tenant_id)
    if not tenant:
        raise AppException(status_code=404, detail="Tenant not found")

    tenant = await tenant_mgmt.toggle_tenant_active(db, tenant)
    status = "activated" if tenant.is_active else "deactivated"
    return ResponseModel(data=TenantResponse.model_validate(tenant), message=f"Tenant {status}")


@router.delete("/{tenant_id}", response_model=CommonResponse)
async def delete_tenant(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    tenant = await tenant_mgmt.get_tenant_by_id(db, tenant_id)
    if not tenant:
        raise AppException(status_code=404, detail="Tenant not found")

    await tenant_mgmt.delete_tenant(db, tenant)
    return ResponseModel(data=None, message="Tenant deleted")