"""
services/permissions.py
All permission business logic.
"""
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.models import Permission
from app.schemas.permission import PermissionCreate


# ── Queries ────────────────────────────────────────────────────────────────────

def get_permission_by_id(db: Session, permission_id: uuid.UUID) -> Permission | None:
    return db.query(Permission).filter(Permission.id == permission_id).first()


def get_permission_by_code(db: Session, code: str) -> Permission | None:
    return db.query(Permission).filter(Permission.code == code).first()


def get_all_permissions(db: Session) -> List[Permission]:
    return db.query(Permission).all()


# ── Mutations ──────────────────────────────────────────────────────────────────

def create_permission(db: Session, perm_in: PermissionCreate) -> Permission:
    perm = Permission(name=perm_in.name, code=perm_in.code, description=perm_in.description)
    db.add(perm)
    db.commit()
    db.refresh(perm)
    return perm


def update_permission(db: Session, perm: Permission, perm_in: PermissionCreate) -> Permission:
    perm.name = perm_in.name
    perm.code = perm_in.code
    perm.description = perm_in.description
    db.commit()
    db.refresh(perm)
    return perm


def delete_permission(db: Session, perm: Permission) -> None:
    db.delete(perm)
    db.commit()