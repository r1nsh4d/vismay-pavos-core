# app/routers/seed.py
from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.database import get_db, engine, Base
from app.models.district import District
from app.models.role import Role
from app.models.tenant import Tenant
from app.models.user import User

# ── import ALL models so Base knows about them before create_all ──────────────
from app.models import tenant, district, role, user, permission, category, set_type, product  # noqa

from app.schemas.common import ResponseModel

router = APIRouter(tags=["Seed"])

SAMPLE_TENANTS = [
    {"name": "Channel Fashion", "code": "CHANNEL_FASHION"}
]

SAMPLE_DISTRICTS = [
    {"name": "Ernakulam", "state": "Kerala"},
    {"name": "Kozhikode", "state": "Kerala"},
    {"name": "Thrissur", "state": "Kerala"},
    {"name": "Thiruvananthapuram", "state": "Kerala"},
]

SYSTEM_ROLES = [
    {"name": "super_admin", "description": "Full system access"},
    {"name": "admin", "description": "Tenant-level admin"},
    {"name": "distributor", "description": "Distributor access"},
    {"name": "executive", "description": "Executive access"},
]

SUPER_ADMIN = {
    "first_name": "Super",
    "last_name": "Admin",
    "username": "superadmin",
    "email": "superadmin@vismay.com",
    "phone": "9999999999",
    "password": "Admin@1234",
}


@router.post("/seed")
async def run_seed(db: AsyncSession = Depends(get_db)):

    # ── Step 1: Create all tables ─────────────────────────────────────────────
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    results = {
        "tables_created": True,
        "tenants": [],
        "districts": [],
        "roles": [],
        "super_admin": None,
    }

    # ── Step 2: Seed tenants ──────────────────────────────────────────────────
    for t_data in SAMPLE_TENANTS:
        existing = await db.scalar(select(Tenant).where(Tenant.code == t_data["code"]))
        if not existing:
            db.add(Tenant(**t_data))
            results["tenants"].append(t_data["code"])
    await db.flush()

    # ── Step 3: Seed districts ────────────────────────────────────────────────
    for d_data in SAMPLE_DISTRICTS:
        existing = await db.scalar(select(District).where(District.name == d_data["name"]))
        if not existing:
            db.add(District(**d_data))
            results["districts"].append(d_data["name"])
    await db.flush()

    # ── Step 4: Seed system roles ─────────────────────────────────────────────
    role_map = {}
    for r_data in SYSTEM_ROLES:
        existing = await db.scalar(
            select(Role).where(Role.name == r_data["name"], Role.tenant_id is None)
        )
        if not existing:
            role = Role(**r_data, tenant_id=None)
            db.add(role)
            await db.flush()
            role_map[r_data["name"]] = role.id
            results["roles"].append(r_data["name"])
        else:
            role_map[r_data["name"]] = existing.id

    # ── Step 5: Seed super admin ──────────────────────────────────────────────
    existing_user = await db.scalar(select(User).where(User.email == SUPER_ADMIN["email"]))
    if not existing_user:
        db.add(User(
            role_id=role_map.get("super_admin"),
            username=SUPER_ADMIN["username"],
            first_name=SUPER_ADMIN["first_name"],
            last_name=SUPER_ADMIN["last_name"],
            email=SUPER_ADMIN["email"],
            phone=SUPER_ADMIN["phone"],
            password_hash=hash_password(SUPER_ADMIN["password"]),
            is_active=True,
            is_verified=True,
            # no tenant_id or district_id — super admin has none
        ))
        await db.flush()
        results["super_admin"] = SUPER_ADMIN["email"]
    else:
        results["super_admin"] = "already exists"

    return ResponseModel(
        data=results,
        message="Seed completed successfully",
    )