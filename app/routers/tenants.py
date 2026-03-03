from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid

from app.database import get_db
from app.schemas.common import CommonResponse, ErrorResponseModel, ResponseModel
from app.schemas.tenant import TenantCreate, TenantResponse
from app.services import tenants as tenant_svc

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.post("", response_model=CommonResponse)
def create_tenant(tenant_in: TenantCreate, db: Session = Depends(get_db)):
    if tenant_svc.get_tenant_by_code(db, tenant_in.code):
        return ErrorResponseModel(code=400, message="Tenant code already exists", error={})

    tenant = tenant_svc.create_tenant(db, tenant_in)
    return ResponseModel(data=TenantResponse.model_validate(tenant), message="Tenant created")


@router.get("", response_model=CommonResponse)
def list_tenants(is_active: bool | None = None, db: Session = Depends(get_db)):
    tenants = tenant_svc.get_all_tenants(db, is_active=is_active)
    return ResponseModel(data=[TenantResponse.model_validate(t) for t in tenants], message="Tenants fetched")


@router.get("/{tenant_id}", response_model=CommonResponse)
def get_tenant(tenant_id: uuid.UUID, db: Session = Depends(get_db)):
    tenant = tenant_svc.get_tenant_by_id(db, tenant_id)
    if not tenant:
        return ErrorResponseModel(code=404, message="Tenant not found", error={})
    return ResponseModel(data=TenantResponse.model_validate(tenant), message="Tenant fetched")


@router.put("/{tenant_id}", response_model=CommonResponse)
def update_tenant(tenant_id: uuid.UUID, tenant_in: TenantCreate, db: Session = Depends(get_db)):
    tenant = tenant_svc.get_tenant_by_id(db, tenant_id)
    if not tenant:
        return ErrorResponseModel(code=404, message="Tenant not found", error={})

    conflict = tenant_svc.get_tenant_by_code(db, tenant_in.code)
    if conflict and conflict.id != tenant_id:
        return ErrorResponseModel(code=400, message="Tenant code already in use", error={})

    tenant = tenant_svc.update_tenant(db, tenant, tenant_in)
    return ResponseModel(data=TenantResponse.model_validate(tenant), message="Tenant updated")


@router.patch("/{tenant_id}/toggle", response_model=CommonResponse)
def toggle_tenant(tenant_id: uuid.UUID, db: Session = Depends(get_db)):
    tenant = tenant_svc.get_tenant_by_id(db, tenant_id)
    if not tenant:
        return ErrorResponseModel(code=404, message="Tenant not found", error={})

    tenant = tenant_svc.toggle_tenant_active(db, tenant)
    status = "activated" if tenant.is_active else "deactivated"
    return ResponseModel(data=TenantResponse.model_validate(tenant), message=f"Tenant {status}")


@router.delete("/{tenant_id}", response_model=CommonResponse)
def delete_tenant(tenant_id: uuid.UUID, db: Session = Depends(get_db)):
    tenant = tenant_svc.get_tenant_by_id(db, tenant_id)
    if not tenant:
        return ErrorResponseModel(code=404, message="Tenant not found", error={})

    tenant_svc.delete_tenant(db, tenant)
    return ResponseModel(data=None, message="Tenant deleted")