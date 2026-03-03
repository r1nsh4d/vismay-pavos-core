"""
services/users.py
All user business logic: CRUD, role/tenant/district assignment,
profile_data management, verify/toggle, password reset.
"""
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.models import User, UserTenant, UserDistrict, Tenant, District, Role, AuthToken
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.services.auth import AuthMgmt


# ── Queries ────────────────────────────────────────────────────────────────────

def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def get_user_by_username_or_email(db: Session, username: str, email: str) -> User | None:
    return db.query(User).filter(
        (User.username == username) | (User.email == email)
    ).first()


def get_all_users(
    db: Session,
    is_active: bool | None = None,
    role_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    district_id: uuid.UUID | None = None,
) -> List[User]:
    query = db.query(User)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    if role_id:
        query = query.filter(User.role_id == role_id)
    if tenant_id:
        query = query.join(UserTenant).filter(
            UserTenant.tenant_id == tenant_id,
            UserTenant.is_active == True,
        )
    if district_id:
        query = query.join(UserDistrict).filter(
            UserDistrict.district_id == district_id,
            UserDistrict.is_active == True,
        )
    return query.all()


# ── Create / Update / Delete ───────────────────────────────────────────────────

def create_user(db: Session, user_in: UserCreate) -> User:
    """
    Creates user row + seeds tenant/district associations.
    profile_data shape by role:
      admin:       {"address", "designation", "department"}
      distributor: {"address", "thaluk", "gst_number"}
      executive:   {"address", "location", "mobile_alternate", "reporting_manager"}
    """
    user = User(
        username=user_in.username,
        first_name=user_in.first_name,
        last_name=user_in.last_name,
        email=user_in.email,
        phone=user_in.phone,
        password_hash=AuthMgmt.get_password_hash(user_in.password),
        role_id=user_in.role_id,
        profile_data=user_in.profile_data,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    db.flush()  # populate user.id

    _seed_tenants(db, user.id, user_in.tenant_ids)
    _seed_districts(db, user.id, user_in.district_ids)

    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user: User, user_in: UserUpdate) -> User:
    if user_in.first_name is not None:
        user.first_name = user_in.first_name
    if user_in.last_name is not None:
        user.last_name = user_in.last_name
    if user_in.phone is not None:
        user.phone = user_in.phone
    if user_in.is_active is not None:
        user.is_active = user_in.is_active
    if user_in.profile_data is not None:
        # Merge so partial updates don't wipe existing fields
        merged = user.profile_data or {}
        merged.update(user_in.profile_data)
        user.profile_data = merged

    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user: User) -> None:
    db.delete(user)
    db.commit()


# ── Role ───────────────────────────────────────────────────────────────────────

def assign_role(db: Session, user: User, role_id: uuid.UUID) -> User | None:
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        return None
    user.role_id = role_id
    db.commit()
    db.refresh(user)
    return user


def remove_role(db: Session, user: User) -> User:
    user.role_id = None
    db.commit()
    db.refresh(user)
    return user


# ── Tenants ────────────────────────────────────────────────────────────────────

def assign_tenants(db: Session, user: User, tenant_ids: List[uuid.UUID]) -> dict:
    existing_ids = {ut.tenant_id for ut in user.user_tenants}
    added, not_found = [], []

    for tid in tenant_ids:
        if tid in existing_ids:
            continue
        if not db.query(Tenant).filter(Tenant.id == tid, Tenant.is_active == True).first():
            not_found.append(str(tid))
            continue
        db.add(UserTenant(user_id=user.id, tenant_id=tid))
        added.append(str(tid))

    db.commit()
    db.refresh(user)
    return {"added": added, "notFound": not_found}


def remove_tenant(db: Session, user_id: uuid.UUID, tenant_id: uuid.UUID) -> bool:
    ut = db.query(UserTenant).filter(
        UserTenant.user_id == user_id,
        UserTenant.tenant_id == tenant_id,
    ).first()
    if not ut:
        return False
    db.delete(ut)
    db.commit()
    return True


def toggle_user_tenant(db: Session, user_id: uuid.UUID, tenant_id: uuid.UUID) -> UserTenant | None:
    ut = db.query(UserTenant).filter(
        UserTenant.user_id == user_id,
        UserTenant.tenant_id == tenant_id,
    ).first()
    if not ut:
        return None
    ut.is_active = not ut.is_active
    db.commit()
    return ut


# ── Districts ──────────────────────────────────────────────────────────────────

def assign_districts(db: Session, user: User, district_ids: List[uuid.UUID]) -> dict:
    existing_ids = {ud.district_id for ud in user.user_districts}
    added, not_found = [], []

    for did in district_ids:
        if did in existing_ids:
            continue
        if not db.query(District).filter(District.id == did).first():
            not_found.append(str(did))
            continue
        db.add(UserDistrict(user_id=user.id, district_id=did))
        added.append(str(did))

    db.commit()
    db.refresh(user)
    return {"added": added, "notFound": not_found}


def remove_district(db: Session, user_id: uuid.UUID, district_id: uuid.UUID) -> bool:
    ud = db.query(UserDistrict).filter(
        UserDistrict.user_id == user_id,
        UserDistrict.district_id == district_id,
    ).first()
    if not ud:
        return False
    db.delete(ud)
    db.commit()
    return True


def toggle_user_district(db: Session, user_id: uuid.UUID, district_id: uuid.UUID) -> UserDistrict | None:
    ud = db.query(UserDistrict).filter(
        UserDistrict.user_id == user_id,
        UserDistrict.district_id == district_id,
    ).first()
    if not ud:
        return None
    ud.is_active = not ud.is_active
    db.commit()
    return ud


# ── Status helpers ─────────────────────────────────────────────────────────────

def verify_user(db: Session, user: User) -> User:
    user.is_verified = True
    db.commit()
    db.refresh(user)
    return user


def toggle_user_active(db: Session, user: User) -> User:
    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    return user


def reset_password(db: Session, user: User, new_password: str) -> User:
    user.password_hash = AuthMgmt.get_password_hash(new_password)
    # Invalidate any active tokens
    token_obj = db.query(AuthToken).filter(
        AuthToken.user_id == user.id,
        AuthToken.is_active == True,
    ).first()
    if token_obj:
        token_obj.is_active = False
    db.commit()
    db.refresh(user)
    return user


# ── Serialization ──────────────────────────────────────────────────────────────

def serialize_user(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        phone=user.phone,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        updated_at=user.updated_at,
        role_id=user.role_id,
        role_name=user.role.name if user.role else None,
        permissions=[rp.permission.code for rp in user.role.role_permissions if rp.permission] if user.role else [],
        user_tenants=[
            {"tenantId": str(ut.tenant_id), "tenantName": ut.tenant.name,
             "tenantCode": ut.tenant.code, "isActive": ut.is_active}
            for ut in user.user_tenants if ut.tenant
        ],
        user_districts=[
            {"districtId": str(ud.district_id), "districtName": ud.district.name,
             "state": ud.district.state, "isActive": ud.is_active}
            for ud in user.user_districts if ud.district
        ],
        profile_data=user.profile_data,
    )


# ── Private helpers ────────────────────────────────────────────────────────────

def _seed_tenants(db: Session, user_id: uuid.UUID, tenant_ids: List[uuid.UUID]) -> None:
    for tid in tenant_ids:
        if db.query(Tenant).filter(Tenant.id == tid, Tenant.is_active == True).first():
            db.add(UserTenant(user_id=user_id, tenant_id=tid))


def _seed_districts(db: Session, user_id: uuid.UUID, district_ids: List[uuid.UUID]) -> None:
    for did in district_ids:
        if db.query(District).filter(District.id == did).first():
            db.add(UserDistrict(user_id=user_id, district_id=did))