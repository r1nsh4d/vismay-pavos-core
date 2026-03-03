"""
services/roles.py
All role & permission-assignment business logic.
"""
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.models import Role, Permission, RolePermission
from app.schemas.role import RoleCreate


# ── Queries ────────────────────────────────────────────────────────────────────

def get_role_by_id(db: Session, role_id: uuid.UUID) -> Role | None:
    return db.query(Role).filter(Role.id == role_id).first()


def get_role_by_name(db: Session, name: str) -> Role | None:
    return db.query(Role).filter(Role.name == name).first()


def get_all_roles(db: Session) -> List[Role]:
    return db.query(Role).all()


# ── Mutations ──────────────────────────────────────────────────────────────────

def create_role(db: Session, role_in: RoleCreate) -> Role:
    role = Role(name=role_in.name, description=role_in.description)
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


def update_role(db: Session, role: Role, role_in: RoleCreate) -> Role:
    role.name = role_in.name
    role.description = role_in.description
    db.commit()
    db.refresh(role)
    return role


def delete_role(db: Session, role: Role) -> None:
    db.delete(role)
    db.commit()


# ── Permission assignment ──────────────────────────────────────────────────────

def assign_permissions_to_role(
    db: Session, role: Role, permission_ids: List[uuid.UUID]
) -> dict:
    existing_ids = {rp.permission_id for rp in role.role_permissions}
    added, not_found = [], []

    for pid in permission_ids:
        if pid in existing_ids:
            continue
        if not db.query(Permission).filter(Permission.id == pid).first():
            not_found.append(str(pid))
            continue
        db.add(RolePermission(role_id=role.id, permission_id=pid))
        added.append(str(pid))

    db.commit()
    db.refresh(role)
    return {"added": added, "notFound": not_found}


def remove_permission_from_role(
    db: Session, role_id: uuid.UUID, permission_id: uuid.UUID
) -> bool:
    rp = db.query(RolePermission).filter(
        RolePermission.role_id == role_id,
        RolePermission.permission_id == permission_id,
    ).first()
    if not rp:
        return False
    db.delete(rp)
    db.commit()
    return True


# ── Serialization helper ───────────────────────────────────────────────────────

def serialize_role(role: Role) -> dict:
    return {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "permissionCodes": [rp.permission.code for rp in role.role_permissions if rp.permission],
    }