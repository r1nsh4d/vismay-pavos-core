from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey,
    String, Text, Numeric, UniqueConstraint
)
from sqlalchemy.orm import relationship, DeclarativeBase


from app.models.base import UUIDPrimaryKey, Base, TimestampMixin
# ─── Tenant ───────────────────────────────────────────────────────────────────


class Tenant(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "tb_tenant"

    name = Column(String(150), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    user_tenants = relationship("UserTenant", back_populates="tenant")
