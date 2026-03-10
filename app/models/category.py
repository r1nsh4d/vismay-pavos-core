import uuid
from typing import Optional
from sqlalchemy import String, ForeignKey, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class Category(BaseModel):
    __tablename__ = "categories"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant = relationship("Tenant", backref="categories")
    set_types = relationship("SetType", back_populates="category", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="category")