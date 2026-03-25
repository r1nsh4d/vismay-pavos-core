from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, engine, Base
from app.schemas.common import ResponseModel
from app.core.security import AuthMgmt

from app.models import (  # noqa: F401
    Permission, RolePermission,
    Role,
    Tenant,
    District,
    User, UserTenant, UserDistrict,
    AuthToken,
    Shop,
    Category,
    SetType, SetTypeItem,
    Product, ProductVariant,
    Stock,
    Order, OrderItem, State, Taluk
)

router = APIRouter(tags=["Seed"])


# ─── Seed data ────────────────────────────────────────────────────────────────

SAMPLE_TENANTS = [
    {"name": "Channel Fashion", "code": "CHANNEL_FASHION"},
    {"name": "Channel Intimates", "code": "CHANNEL_INTIMATES"},
    {"name": "Shop In Shop", "code": "SIS"},
    {"name": "Retail or EBO", "code": "RETAIL"}
]

KERALA_STATE = {"name": "Kerala", "code": "KL"}

KERALA_DISTRICTS_TALUKS = [
    {
        "name": "Thiruvananthapuram",
        "taluks": ["Thiruvananthapuram", "Chirayinkeezhu", "Nedumangad", "Neyyattinkara", "Varkala", "Kattakada"],
    },
    {
        "name": "Kollam",
        "taluks": ["Kollam", "Kunnathur", "Kottarakkara", "Pathanapuram", "Punalur", "Karunagappally"],
    },
    {
        "name": "Pathanamthitta",
        "taluks": ["Pathanamthitta", "Adoor", "Kozhencherry", "Mallappally", "Ranni", "Thiruvalla"],
    },
    {
        "name": "Alappuzha",
        "taluks": ["Alappuzha", "Ambalappuzha", "Chengannur", "Karthikappally", "Kuttanad", "Mavelikkara"],
    },
    {
        "name": "Kottayam",
        "taluks": ["Kottayam", "Changanassery", "Kanjirappally", "Meenachil", "Vaikom"],
    },
    {
        "name": "Idukki",
        "taluks": ["Devikulam", "Idukki", "Peermade", "Thodupuzha", "Udumbanchola"],
    },
    {
        "name": "Ernakulam",
        "taluks": ["Aluva", "Kanayannur", "Kochi", "Kothamangalam", "Kunnathunad", "Muvattupuzha", "Paravur"],
    },
    {
        "name": "Thrissur",
        "taluks": ["Chalakudy", "Kodungallur", "Mukundapuram", "Talappilly", "Thrissur"],
    },
    {
        "name": "Palakkad",
        "taluks": ["Alathur", "Attappady", "Chittur", "Mannarkkad", "Palakkad", "Pattambi", "Thrithala"],
    },
    {
        "name": "Malappuram",
        "taluks": ["Ernad", "Kondotty", "Manjeri", "Nilambur", "Perinthalmanna", "Ponnani", "Tirur", "Tirurangadi"],
    },
    {
        "name": "Kozhikode",
        "taluks": ["Koyilandy", "Kozhikode", "Mukkom", "Thamarassery", "Vadakara"],
    },
    {
        "name": "Wayanad",
        "taluks": ["Mananthavady", "Sultan Bathery", "Vythiri"],
    },
    {
        "name": "Kannur",
        "taluks": ["Iritty", "Kannur", "Taliparamba", "Thalassery"],
    },
    {
        "name": "Kasaragod",
        "taluks": ["Hosdurg", "Kasaragod", "Manjeshwar", "Velu"],
    },
]

SYSTEM_ROLES = [
    {"name": "super_admin", "description": "Full system access"},
    {"name": "admin",       "description": "Tenant-level admin"},
    {"name": "scm_user",    "description": "SCM access — same as admin but cannot manage admin users"},
    {"name": "distributor", "description": "Distributor access"},
    {"name": "executive",   "description": "Executive access"},
]

MODULES = [
    "tenants", "users", "roles", "permissions",
    "categories", "set_types", "products",
    "shops", "stocks", "orders", "reports", "dashboard",
    "states", "districts", "taluks",
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

# All permissions except admin user management
# Replace SCM_EXCLUDED_PERMISSIONS and FULL_ACCESS_ROLES section with this:

FULL_ACCESS_ROLES = {"super_admin", "admin"}

SCM_EXCLUDED_PERMISSIONS = {
    "users:create",
    "users:update",
    "users:delete",
    "roles:create",
    "roles:update",
    "roles:delete",
}

DISTRIBUTOR_PERMISSIONS = {
    # Products - read only
    "products:read",
    # Shops - manage own shop
    "shops:read",
    "shops:create",
    "shops:update",
    # Orders - full order management
    "orders:read",
    "orders:create",
    "orders:update",
    "orders:delete",
    # Stocks - read only
    "stocks:read",
    # Categories & set types - read only
    "categories:read",
    "set_types:read",
    # Dashboard & reports - read only
    "dashboard:read",
    "reports:read",
}

EXECUTIVE_PERMISSIONS = {
    # Products - read only
    "products:read",
    # Shops - read and update
    "shops:read",
    "shops:update",
    # Orders - full order management
    "orders:read",
    "orders:create",
    "orders:update",
    # Stocks - read only
    "stocks:read",
    # Categories & set types - read only
    "categories:read",
    "set_types:read",
    # Dashboard & reports
    "dashboard:read",
    "reports:read",
}

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
    await db.commit()

    results = {
        "tables_created":            True,
        "state":                     None,
        "districts":                 [],
        "taluks":                    [],
        "tenants":                   [],
        "roles":                     [],
        "permissions_seeded":        [],
        "role_permissions_assigned": {},
        "super_admin":               None,
        "super_admin_tenants": []
    }

    # Step 2: Seed Kerala state
    kerala = await db.scalar(select(State).where(State.code == KERALA_STATE["code"]))
    if not kerala:
        kerala = State(**KERALA_STATE)
        db.add(kerala)
        await db.flush()
        results["state"] = "Kerala created"
    else:
        results["state"] = "Kerala already exists"

    # Step 3: Seed districts + taluks for Kerala
    for d_data in KERALA_DISTRICTS_TALUKS:
        district = await db.scalar(
            select(District).where(District.name == d_data["name"], District.state_id == kerala.id)
        )
        if not district:
            district = District(name=d_data["name"], state_id=kerala.id, is_active=True)
            db.add(district)
            await db.flush()
            results["districts"].append(d_data["name"])

        for taluk_name in d_data["taluks"]:
            taluk_exists = await db.scalar(
                select(Taluk).where(Taluk.name == taluk_name, Taluk.district_id == district.id)
            )
            if not taluk_exists:
                db.add(Taluk(name=taluk_name, district_id=district.id, is_active=True))
                results["taluks"].append(f"{d_data['name']} → {taluk_name}")

        await db.flush()

    # Step 4: Seed tenants
    for t_data in SAMPLE_TENANTS:
        exists = await db.scalar(select(Tenant).where(Tenant.code == t_data["code"]))
        if not exists:
            db.add(Tenant(**t_data))
            results["tenants"].append(t_data["code"])
    await db.flush()

    # Step 5: Seed roles
    role_map: dict = {}
    for r_data in SYSTEM_ROLES:
        role = await db.scalar(select(Role).where(Role.name == r_data["name"]))
        if not role:
            role = Role(**r_data)
            db.add(role)
            await db.flush()
            results["roles"].append(r_data["name"])
        role_map[r_data["name"]] = role.id

    # Step 6: Seed permissions
    permission_map: dict = {}
    for p_data in ALL_PERMISSIONS:
        perm = await db.scalar(select(Permission).where(Permission.code == p_data["code"]))
        if not perm:
            perm = Permission(**p_data)
            db.add(perm)
            await db.flush()
            results["permissions_seeded"].append(p_data["code"])
        permission_map[p_data["code"]] = perm.id

    # Step 7: Assign permissions to roles
    # super_admin + admin → all permissions
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

    # scm_user → all permissions except admin management
    scm_role_id = role_map.get("scm_user")
    if scm_role_id:
        assigned = 0
        for perm_code, perm_id in permission_map.items():
            if perm_code in SCM_EXCLUDED_PERMISSIONS:
                continue
            exists = await db.scalar(
                select(RolePermission).where(
                    RolePermission.role_id == scm_role_id,
                    RolePermission.permission_id == perm_id,
                )
            )
            if not exists:
                db.add(RolePermission(role_id=scm_role_id, permission_id=perm_id))
                assigned += 1
        await db.flush()
        results["role_permissions_assigned"]["scm_user"] = assigned

    # distributor → limited permissions
    distributor_role_id = role_map.get("distributor")
    if distributor_role_id:
        assigned = 0
        for perm_code, perm_id in permission_map.items():
            if perm_code not in DISTRIBUTOR_PERMISSIONS:
                continue
            exists = await db.scalar(
                select(RolePermission).where(
                    RolePermission.role_id == distributor_role_id,
                    RolePermission.permission_id == perm_id,
                )
            )
            if not exists:
                db.add(RolePermission(role_id=distributor_role_id, permission_id=perm_id))
                assigned += 1
        await db.flush()
        results["role_permissions_assigned"]["distributor"] = assigned

    # executive → limited permissions
    executive_role_id = role_map.get("executive")
    if executive_role_id:
        assigned = 0
        for perm_code, perm_id in permission_map.items():
            if perm_code not in EXECUTIVE_PERMISSIONS:
                continue
            exists = await db.scalar(
                select(RolePermission).where(
                    RolePermission.role_id == executive_role_id,
                    RolePermission.permission_id == perm_id,
                )
            )
            if not exists:
                db.add(RolePermission(role_id=executive_role_id, permission_id=perm_id))
                assigned += 1
        await db.flush()
        results["role_permissions_assigned"]["executive"] = assigned

    # Step 8: Seed super admin user
    exists = await db.scalar(select(User).where(User.email == SUPER_ADMIN["email"]))
    if not exists:
        super_user = User(
            role_id=role_map.get("super_admin"),
            username=SUPER_ADMIN["username"],
            first_name=SUPER_ADMIN["first_name"],
            last_name=SUPER_ADMIN["last_name"],
            email=SUPER_ADMIN["email"],
            phone=SUPER_ADMIN["phone"],
            password_hash=AuthMgmt.get_password_hash(SUPER_ADMIN["password"]),
            is_active=True,
            is_verified=True,
        )
        db.add(super_user)
        await db.flush()

        # Assign all tenants to super admin
        all_tenants = (await db.execute(select(Tenant))).scalars().all()
        for tenant in all_tenants:
            db.add(UserTenant(user_id=super_user.id, tenant_id=tenant.id, is_active=True))
        await db.flush()

        results["super_admin"] = SUPER_ADMIN["email"]
        results["super_admin_tenants"] = [t.code for t in all_tenants]
    else:
        results["super_admin"] = "already exists"

    await db.commit()

    return ResponseModel(
        data=results,
        message="Seed completed successfully",
    )