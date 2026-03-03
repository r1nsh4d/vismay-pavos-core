from sqlalchemy.orm import Session

from app.core.security import AuthMgmt
from app.models import User, AuthToken
from app.schemas.user import UserCreate


# ── Register ───────────────────────────────────────────────────────────────────

def get_user_by_username_or_email(db: Session, username: str, email: str) -> User | None:
    return db.query(User).filter(
        (User.username == username) | (User.email == email)
    ).first()


def create_user_record(db: Session, user_in: UserCreate) -> User:
    """Creates user + assigns tenants/districts. Does NOT commit."""
    from app.models import UserTenant, UserDistrict, Tenant, District

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
    db.flush()  # get user.id before associations

    for tenant_id in user_in.tenant_ids:
        if db.query(Tenant).filter(Tenant.id == tenant_id, Tenant.is_active == True).first():
            db.add(UserTenant(user_id=user.id, tenant_id=tenant_id))

    for district_id in user_in.district_ids:
        if db.query(District).filter(District.id == district_id).first():
            db.add(UserDistrict(user_id=user.id, district_id=district_id))

    return user


# ── Login ──────────────────────────────────────────────────────────────────────

def authenticate(db: Session, login: str, password: str) -> User | None:
    return AuthMgmt.authenticate_user(db, login=login, password=password)


def issue_token_pair(db: Session, user_id) -> dict:
    """Creates and stores a fresh access+refresh token pair."""
    access = AuthMgmt.create_access_token(db=db, user_id=user_id)
    refresh = AuthMgmt.create_refresh_token(db=db, user_id=user_id)
    AuthMgmt.store_refresh_token(db=db, user_id=user_id, refresh_token=refresh)
    return {"accessToken": access, "refreshToken": refresh, "tokenType": "bearer"}


# ── Refresh / Logout ───────────────────────────────────────────────────────────

def validate_refresh(db: Session, refresh_token: str):
    """Returns user_id or None."""
    return AuthMgmt.validate_refresh_token(db, refresh_token)


def revoke_refresh_token(db: Session, user_id) -> bool:
    token_obj = db.query(AuthToken).filter(
        AuthToken.user_id == user_id,
        AuthToken.is_active == True,
    ).first()
    if not token_obj:
        return False
    token_obj.is_active = False
    db.commit()
    return True