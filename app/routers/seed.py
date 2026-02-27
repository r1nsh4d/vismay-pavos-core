from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.database import get_db, engine, Base
from app.models.district import District
from app.models.role import Role
from app.models.tenant import Tenant
from app.models.user import User
from app.models.permission import Permission, RolePermission

# ── import ALL models so Base knows about them before create_all ──────────────
from app.models import (  # noqa
    tenant, district, role, user, permission,
    category, set_type, product, shop, stock, order
)

from app.schemas.common import ResponseModel

router = APIRouter(tags=["Seed"])

SAMPLE_TENANTS = [
    {"name": "Channel Fashion", "code": "CHANNEL_FASHION"}
]

SAMPLE_DISTRICTS = [
    {"name": "Thiruvananthapuram", "state": "Kerala"},
    {"name": "Kollam", "state": "Kerala"},
    {"name": "Pathanamthitta", "state": "Kerala"},
    {"name": "Alappuzha", "state": "Kerala"},
    {"name": "Kottayam", "state": "Kerala"},
    {"name": "Idukki", "state": "Kerala"},
    {"name": "Ernakulam", "state": "Kerala"},
    {"name": "Thrissur", "state": "Kerala"},
    {"name": "Palakkad", "state": "Kerala"},
    {"name": "Malappuram", "state": "Kerala"},
    {"name": "Kozhikode", "state": "Kerala"},
    {"name": "Wayanad", "state": "Kerala"},
    {"name": "Kannur", "state": "Kerala"},
    {"name": "Kasaragod", "state": "Kerala"},
]

SYSTEM_ROLES = [
    {"name": "super_admin", "description": "Full system access"},
    {"name": "admin", "description": "Tenant-level admin"},
    {"name": "distributor", "description": "Distributor access"},
    {"name": "executive", "description": "Executive access"},
]

# ── All permissions: module:action ───────────────────────────────────────────
MODULES = [
    "tenants",
    "users",
    "roles",
    "permissions",
    "categories",
    "set_types",
    "products",
    "shops",
    "stocks",
    "orders",
    "reports",
    "dashboard"
]
ACTIONS = ["read", "create", "update", "delete"]

ALL_PERMISSIONS = [
    {
        "name": f"{module}:{action}",
        "code": f"{module}:{action}",
        "description": f"{action.capitalize()} {module}",
    }
    for module in MODULES
    for action in ACTIONS
]

SUPER_ADMIN = {
    "first_name": "Super",
    "last_name": "Admin",
    "username": "superadmin",
    "email": "superadmin@vismay.com",
    "phone": "9999999999",
    "password": "Admin@1234",
}

#ignore
ADMIN ={
  "username": "amaanShah",
  "first_name": "Amaan",
  "last_name": "Shah",
  "email": "amaancreate@gmail.com",
  "phone": "7907236085",
  "password": "password",
  "is_active": True,
  "is_verified": False,
  "tenant_ids": [],
  "district_ids": []
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
        "permissions_seeded": [],
        "super_admin_permissions_assigned": 0,
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
            select(Role).where(Role.name == r_data["name"], Role.tenant_id == None)
        )
        if not existing:
            role = Role(**r_data, tenant_id=None)
            db.add(role)
            await db.flush()
            role_map[r_data["name"]] = role.id
            results["roles"].append(r_data["name"])
        else:
            role_map[r_data["name"]] = existing.id

    # ── Step 5: Seed all permissions ──────────────────────────────────────────
    permission_map = {}  # code → permission.id
    for p_data in ALL_PERMISSIONS:
        existing = await db.scalar(
            select(Permission).where(Permission.code == p_data["code"])
        )
        if not existing:
            perm = Permission(**p_data)
            db.add(perm)
            await db.flush()
            permission_map[p_data["code"]] = perm.id
            results["permissions_seeded"].append(p_data["code"])
        else:
            permission_map[p_data["code"]] = existing.id

    # ── Step 6: Assign ALL permissions to super_admin role ────────────────────
    super_admin_role_id = role_map.get("super_admin")
    if super_admin_role_id:
        assigned_count = 0
        for perm_code, perm_id in permission_map.items():
            existing = await db.scalar(
                select(RolePermission).where(
                    RolePermission.role_id == super_admin_role_id,
                    RolePermission.permission_id == perm_id,
                )
            )
            if not existing:
                db.add(RolePermission(
                    role_id=super_admin_role_id,
                    permission_id=perm_id,
                ))
                assigned_count += 1
        await db.flush()
        results["super_admin_permissions_assigned"] = assigned_count

    admin_role_id = role_map.get("admin")
    if admin_role_id:
        assigned_count = 0
        for perm_code, perm_id in permission_map.items():
            existing = await db.scalar(
                select(RolePermission).where(
                    RolePermission.role_id == admin_role_id,
                    RolePermission.permission_id == perm_id,
                )
            )
            if not existing:
                db.add(RolePermission(
                    role_id=admin_role_id,
                    permission_id=perm_id,
                ))
                assigned_count += 1
        await db.flush()
        results["admin_permissions_assigned"] = assigned_count

    # ── Step 7: Seed super admin user ─────────────────────────────────────────
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
        ))
        await db.flush()
        results["super_admin"] = SUPER_ADMIN["email"]
    else:
        results["super_admin"] = "already exists"

    return ResponseModel(
        data=results,
        message="Seed completed successfully",
    )
