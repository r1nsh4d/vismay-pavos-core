from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional

from app.models.base import BaseModel


# Permissions
class Permission(BaseModel):
    __tablename__ = "permissions"
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)

    role_permissions = relationship("RolePermission", back_populates="permission")