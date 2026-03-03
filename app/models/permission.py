from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey,
    String, Text, Numeric, UniqueConstraint
)
from sqlalchemy.orm import relationship, DeclarativeBase

# ─── Permission ───────────────────────────────────────────────────────────────
from app.models.base import UUIDPrimaryKey, TimestampMixin, Base


class Permission(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "tb_permission"

    name = Column(String(100), nullable=False)
    code = Column(String(100), unique=True, nullable=False)  # e.g. "orders:create"
    description = Column(Text, nullable=True)

    role_permissions = relationship("RolePermission", back_populates="permission")