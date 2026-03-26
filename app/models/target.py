import uuid
import enum
from typing import Optional
from sqlalchemy import ForeignKey, Integer, Numeric, String, Enum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class TargetType(str, enum.Enum):
    order_count = "order_count"
    order_value = "order_value"


class ExecutiveTarget(BaseModel):
    __tablename__ = "executive_targets"

    __table_args__ = (
        UniqueConstraint("user_id", "year", "month", "target_type", name="uq_executive_target"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    target_type: Mapped[TargetType] = mapped_column(Enum(TargetType, native_enum=False), nullable=False)
    target_value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    user = relationship("User", backref="targets")
    tenant = relationship("Tenant", backref="executive_targets")