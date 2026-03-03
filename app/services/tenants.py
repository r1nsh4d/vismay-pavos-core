"""
services/tenants.py
All tenant business logic.
"""
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.models import Tenant
from app.schemas.tenant import TenantCreate


# ── Queries ────────────────────────────────────────────────────────────────────

def get_tenant_by_id(db: Session, tenant_id: uuid.UUID) -> Tenant | None:
    return db.query(Tenant).filter(Tenant.id == tenant_id).first()


def get_tenant_by_code(db: Session, code: str) -> Tenant | None:
    return db.query(Tenant).filter(Tenant.code == code).first()


def get_all_tenants(db: Session, is_active: bool | None = None) -> List[Tenant]:
    query = db.query(Tenant)
    if is_active is not None:
        query = query.filter(Tenant.is_active == is_active)
    return query.all()


# ── Mutations ──────────────────────────────────────────────────────────────────

def create_tenant(db: Session, tenant_in: TenantCreate) -> Tenant:
    tenant = Tenant(name=tenant_in.name, code=tenant_in.code)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def update_tenant(db: Session, tenant: Tenant, tenant_in: TenantCreate) -> Tenant:
    tenant.name = tenant_in.name
    tenant.code = tenant_in.code
    db.commit()
    db.refresh(tenant)
    return tenant


def toggle_tenant_active(db: Session, tenant: Tenant) -> Tenant:
    tenant.is_active = not tenant.is_active
    db.commit()
    db.refresh(tenant)
    return tenant


def delete_tenant(db: Session, tenant: Tenant) -> None:
    db.delete(tenant)
    db.commit()