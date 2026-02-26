from __future__ import annotations
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text, TIMESTAMP, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base, pk_type

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.district import District
    from app.models.role import Role
    from app.models.auth_token import AuthToken
    from app.models.shop import Shop


class UserTenant(Base):
    """Junction — one user can belong to many tenants"""
    __tablename__ = "user_tenants"
    __table_args__ = (UniqueConstraint("user_id", "tenant_id", name="uq_user_tenant"),)

    id: Mapped[int] = mapped_column(pk_type(), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))
    created_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now())

    user: Mapped[User] = relationship("User", back_populates="user_tenants")
    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="user_tenants")


class UserDistrict(Base):
    """Junction — one user can belong to many districts"""
    __tablename__ = "user_districts"
    __table_args__ = (UniqueConstraint("user_id", "district_id", name="uq_user_district"),)

    id: Mapped[int] = mapped_column(pk_type(), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id", ondelete="CASCADE"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))
    created_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now())

    user: Mapped[User] = relationship("User", back_populates="user_districts")
    district: Mapped[District] = relationship("District", back_populates="user_districts")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(pk_type(), primary_key=True, autoincrement=True)
    role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id"), nullable=True)

    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))

    created_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    role: Mapped[Role] = relationship("Role", back_populates="users")
    auth_tokens: Mapped[list[AuthToken]] = relationship("AuthToken", back_populates="user", cascade="all, delete")
    shops: Mapped[list[Shop]] = relationship("Shop", back_populates="created_by_user")
    user_tenants: Mapped[list[UserTenant]] = relationship("UserTenant", back_populates="user", cascade="all, delete")
    user_districts: Mapped[list[UserDistrict]] = relationship("UserDistrict", back_populates="user", cascade="all, delete")