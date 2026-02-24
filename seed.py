"""
Seed script — creates initial super-admin user and sample tenants.
Run: python seed.py
"""
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.security import hash_password
from app.database import AsyncSessionLocal
from app.models.tenant import Tenant
from app.models.district import District
from app.models.role import Role
from app.models.user import User


SAMPLE_TENANTS = [
    {"name": "Channel Fashion", "code": "CHANNEL_FASHION"},
    {"name": "Channel Intimates", "code": "CHANNEL_INTIMATES"},
    {"name": "SIS", "code": "SIS"},
    {"name": "SOR", "code": "SOR"},
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
    {"name": "executive", "description": "Executive (read-only) access"},
]

SUPER_ADMIN = {
    "first_name": "Super",
    "last_name": "Admin",
    "email": "superadmin@vismay.com",
    "phone": "9999999999",
    "password": "Admin@1234",
}


async def seed():
    async with AsyncSessionLocal() as db:
        try:
            print("🌱 Seeding tenants...")
            for t_data in SAMPLE_TENANTS:
                existing = await db.scalar(select(Tenant).where(Tenant.code == t_data["code"]))
                if not existing:
                    db.add(Tenant(**t_data))
            await db.flush()

            print("🌱 Seeding districts...")
            for d_data in SAMPLE_DISTRICTS:
                existing = await db.scalar(select(District).where(District.name == d_data["name"]))
                if not existing:
                    db.add(District(**d_data))
            await db.flush()

            print("🌱 Seeding system roles (no tenant)...")
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
                else:
                    role_map[r_data["name"]] = existing.id

            print("🌱 Seeding super admin user...")
            existing_user = await db.scalar(select(User).where(User.email == SUPER_ADMIN["email"]))
            if not existing_user:
                db.add(User(
                    tenant_id=None,
                    role_id=role_map.get("super_admin"),
                    first_name=SUPER_ADMIN["first_name"],
                    last_name=SUPER_ADMIN["last_name"],
                    email=SUPER_ADMIN["email"],
                    phone=SUPER_ADMIN["phone"],
                    password_hash=hash_password(SUPER_ADMIN["password"]),
                    is_active=True,
                    is_verified=True,
                ))
                await db.flush()

            await db.commit()
            print("✅ Seeding complete!")
            print(f"\n👤 Super Admin Login:")
            print(f"   Email   : {SUPER_ADMIN['email']}")
            print(f"   Password: {SUPER_ADMIN['password']}")

        except Exception as e:
            await db.rollback()
            print(f"❌ Seeding failed: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(seed())
