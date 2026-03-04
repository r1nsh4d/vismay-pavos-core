from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, engine, Base
from app.schemas.common import ResponseModel
from app.core.security import AuthMgmt

# ── Import ALL models so Base.metadata knows about them before create_all ─────
from app.models import (  # noqa: F401
    Permission, RolePermission,
    Role,
    Tenant,
    District,
    User, UserTenant, UserDistrict,
    AuthToken
)

router = APIRouter(tags=["Seed"])

# ─── Seed data ────────────────────────────────────────────────────────────────

SAMPLE_TENANTS = [
    {"name": "Channel Fashion", "code": "CHANNEL_FASHION"},
]

SAMPLE_DISTRICTS = [
    {"name": "Thiruvananthapuram", "state": "Kerala"},
    {"name": "Kollam",             "state": "Kerala"},
    {"name": "Pathanamthitta",     "state": "Kerala"},
    {"name": "Alappuzha",          "state": "Kerala"},
    {"name": "Kottayam",           "state": "Kerala"},
    {"name": "Idukki",             "state": "Kerala"},
    {"name": "Ernakulam",          "state": "Kerala"},
    {"name": "Thrissur",           "state": "Kerala"},
    {"name": "Palakkad",           "state": "Kerala"},
    {"name": "Malappuram",         "state": "Kerala"},
    {"name": "Kozhikode",          "state": "Kerala"},
    {"name": "Wayanad",            "state": "Kerala"},
    {"name": "Kannur",             "state": "Kerala"},
    {"name": "Kasaragod",          "state": "Kerala"},
]

SYSTEM_ROLES = [
    {"name": "super_admin",  "description": "Full system access"},
    {"name": "admin",        "description": "Tenant-level admin"},
    {"name": "distributor",  "description": "Distributor access"},
    {"name": "executive",    "description": "Executive access"},
]

MODULES = [
    "tenants", "users", "roles", "permissions",
    "categories", "set_types", "products",
    "shops", "stocks", "orders", "reports", "dashboard",
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

# Roles that receive ALL permissions at seed time
FULL_ACCESS_ROLES = {"super_admin", "admin"}

SUPER_ADMIN = {
    "username":   "superadmin",
    "first_name": "Super",
    "last_name":  "Admin",
    "email":      "superadmin@vismay.com",
    "phone":      "9999999999",
    "password":   "Admin@1234",
}


# ─── Route ────────────────────────────────────────────────────────────────────

@router.post("/seed")
async def run_seed(db: AsyncSession = Depends(get_db)):

    # Step 1: Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # engine.begin() auto-commits on exit, but we also need
    # to expire the session so it sees the new tables
    await db.commit()

    results = {
        "tables_created":            True,
        "tenants":                   [],
        "districts":                 [],
        "roles":                     [],
        "permissions_seeded":        [],
        "role_permissions_assigned": {},
        "super_admin":               None,
    }

    # Step 2: Seed tenants
    for t_data in SAMPLE_TENANTS:
        exists = await db.scalar(select(Tenant).where(Tenant.code == t_data["code"]))
        if not exists:
            db.add(Tenant(**t_data))
            results["tenants"].append(t_data["code"])
    await db.flush()

    # Step 3: Seed districts
    for d_data in SAMPLE_DISTRICTS:
        exists = await db.scalar(select(District).where(District.name == d_data["name"]))
        if not exists:
            db.add(District(**d_data))
            results["districts"].append(d_data["name"])
    await db.flush()

    # Step 4: Seed roles
    role_map: dict = {}
    for r_data in SYSTEM_ROLES:
        exists = await db.scalar(select(Role).where(Role.name == r_data["name"]))
        if not exists:
            role = Role(**r_data)
            db.add(role)
            await db.flush()
            role_map[r_data["name"]] = role.id
            results["roles"].append(r_data["name"])
        else:
            role_map[r_data["name"]] = exists.id

    # Step 5: Seed permissions
    permission_map: dict = {}
    for p_data in ALL_PERMISSIONS:
        exists = await db.scalar(select(Permission).where(Permission.code == p_data["code"]))
        if not exists:
            perm = Permission(**p_data)
            db.add(perm)
            await db.flush()
            permission_map[p_data["code"]] = perm.id
            results["permissions_seeded"].append(p_data["code"])
        else:
            permission_map[p_data["code"]] = exists.id

    # Step 6: Assign all permissions to full-access roles
    for role_name in FULL_ACCESS_ROLES:
        role_id = role_map.get(role_name)
        if not role_id:
            continue

        assigned = 0
        for perm_id in permission_map.values():
            exists = await db.scalar(
                select(RolePermission).where(
                    RolePermission.role_id == role_id,
                    RolePermission.permission_id == perm_id,
                )
            )
            if not exists:
                db.add(RolePermission(role_id=role_id, permission_id=perm_id))
                assigned += 1

        await db.flush()
        results["role_permissions_assigned"][role_name] = assigned

    # Step 7: Seed super admin user
    exists = await db.scalar(select(User).where(User.email == SUPER_ADMIN["email"]))
    if not exists:
        db.add(User(
            role_id=role_map.get("super_admin"),
            username=SUPER_ADMIN["username"],
            first_name=SUPER_ADMIN["first_name"],
            last_name=SUPER_ADMIN["last_name"],
            email=SUPER_ADMIN["email"],
            phone=SUPER_ADMIN["phone"],
            password_hash=AuthMgmt.get_password_hash(SUPER_ADMIN["password"]),
            is_active=True,
            is_verified=True,
        ))
        await db.flush()
        results["super_admin"] = SUPER_ADMIN["email"]
    else:
        results["super_admin"] = "already exists"

    await db.commit()

    return ResponseModel(
        data=results,
        message="Seed completed successfully",
    )