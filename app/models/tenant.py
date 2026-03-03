from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.models.base import BaseModel


# Tenants
class Tenant(BaseModel):
    __tablename__ = "tenants"
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user_tenants = relationship("UserTenant", back_populates="tenant")