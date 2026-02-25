from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text, TIMESTAMP, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base, pk_type


if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.permission import RolePermission

class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)

    id: Mapped[int] = mapped_column(pk_type(), primary_key=True, autoincrement=True)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))
    created_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now())

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="roles")
    users: Mapped[list["User"]] = relationship("User", back_populates="role")
    role_permissions: Mapped[list["RolePermission"]] = relationship("RolePermission", back_populates="role", cascade="all, delete")
