from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey,
    String, Text, Numeric, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, DeclarativeBase


# ─── Role ─────────────────────────────────────────────────────────────────────
from app.models.base import UUIDPrimaryKey, Base, TimestampMixin


class Role(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "tb_role"

    name = Column(String(100), unique=True, nullable=False)  # ADMIN, DISTRIBUTOR, EXECUTIVE
    description = Column(Text, nullable=True)

    role_permissions = relationship("RolePermission", back_populates="role")
    users = relationship("User", back_populates="role")


# ─── Role <-> Permission ──────────────────────────────────────────────────────

class RolePermission(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "tb_role_permission"
    __table_args__ = (UniqueConstraint("role_id", "permission_id"),)

    role_id = Column(UUID(as_uuid=True), ForeignKey("tb_role.id", ondelete="CASCADE"), nullable=False)
    permission_id = Column(UUID(as_uuid=True), ForeignKey("tb_permission.id", ondelete="CASCADE"), nullable=False)

    role = relationship("Role", back_populates="role_permissions")
    permission = relationship("Permission", back_populates="role_permissions")