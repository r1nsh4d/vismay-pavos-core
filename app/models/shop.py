from __future__ import annotations
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text, TIMESTAMP, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, pk_type

if TYPE_CHECKING:
    from app.models.district import District
    from app.models.user import User


class Shop(Base):
    __tablename__ = "shops"

    id: Mapped[int] = mapped_column(pk_type(), primary_key=True, autoincrement=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id", ondelete="CASCADE"), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)  # area/landmark
    contact: Mapped[str | None] = mapped_column(String(20), nullable=True)    # phone number
    contact_person: Mapped[str | None] = mapped_column(String(150), nullable=True)
    gst_number: Mapped[str | None] = mapped_column(String(20), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    district: Mapped[District] = relationship("District", back_populates="shops")
    created_by_user: Mapped[User] = relationship("User", back_populates="shops")