from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey,
    String, Text, Numeric, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy.orm import relationship, DeclarativeBase

from app.models.base import UUIDPrimaryKey, TimestampMixin, Base
# ─── User ─────────────────────────────────────────────────────────────────────

class User(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "tb_user"

    username = Column(String(100), unique=True, nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=True)
    email = Column(String(255), unique=True, nullable=False)
    phone = Column(String(20), nullable=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)

    role_id = Column(UUID(as_uuid=True), ForeignKey("tb_role.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    role = relationship("Role", back_populates="users")
    user_tenants = relationship("UserTenant", back_populates="user", cascade="all, delete-orphan")
    user_districts = relationship("UserDistrict", back_populates="user", cascade="all, delete-orphan")
    auth_tokens = relationship("AuthToken", back_populates="user", cascade="all, delete-orphan")

    # Role-specific profile (one of these will be populated)
    admin_profile = relationship("AdminProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    distributor_profile = relationship("DistributorProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    executive_profile = relationship("ExecutiveProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")


# ─── User <-> Tenant ──────────────────────────────────────────────────────────

class UserTenant(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "tb_user_tenant"
    __table_args__ = (UniqueConstraint("user_id", "tenant_id"),)

    user_id = Column(UUID(as_uuid=True), ForeignKey("tb_user.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tb_tenant.id", ondelete="CASCADE"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="user_tenants")
    tenant = relationship("Tenant", back_populates="user_tenants")


# ─── User <-> District ────────────────────────────────────────────────────────

class UserDistrict(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "tb_user_district"
    __table_args__ = (UniqueConstraint("user_id", "district_id"),)

    user_id = Column(UUID(as_uuid=True), ForeignKey("tb_user.id", ondelete="CASCADE"), nullable=False)
    district_id = Column(UUID(as_uuid=True), ForeignKey("tb_district.id", ondelete="CASCADE"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="user_districts")
    district = relationship("District", back_populates="user_districts")


# ─── Admin Profile ────────────────────────────────────────────────────────────

class AdminProfile(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "tb_admin"

    user_id = Column(UUID(as_uuid=True), ForeignKey("tb_user.id", ondelete="CASCADE"), unique=True, nullable=False)
    department_name = Column(String(150), nullable=True)
    address = Column(Text, nullable=True)
    phone = Column(String(20), nullable=True)

    user = relationship("User", back_populates="admin_profile")


# ─── Distributor Profile ──────────────────────────────────────────────────────

class DistributorProfile(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "tb_distributor"

    user_id = Column(UUID(as_uuid=True), ForeignKey("tb_user.id", ondelete="CASCADE"), unique=True, nullable=False)
    company_name = Column(String(150), nullable=True)
    gst = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    state = Column(String(100), nullable=True)
    pincode = Column(String(10), nullable=True)
    taluk = Column(String(100), nullable=True)

    user = relationship("User", back_populates="distributor_profile")


# ─── Executive Profile ────────────────────────────────────────────────────────

class ExecutiveProfile(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "tb_executive"

    user_id = Column(UUID(as_uuid=True), ForeignKey("tb_user.id", ondelete="CASCADE"), unique=True, nullable=False)
    designation = Column(String(100), nullable=True)
    address = Column(Text, nullable=True)
    phone = Column(String(20), nullable=True)
    pincode = Column(String(10), nullable=True)
    latitude = Column(Numeric(9, 6), nullable=True)   # GPS
    longitude = Column(Numeric(9, 6), nullable=True)  # GPS

    # Reporting admin (points to a User with admin role)
    reporting_admin_id = Column(UUID(as_uuid=True), ForeignKey("tb_user.id", ondelete="SET NULL"), nullable=True)
    reporting_admin = relationship("User", foreign_keys=[reporting_admin_id])

    user = relationship("User", back_populates="executive_profile", foreign_keys=[user_id])