import uuid
from typing import Optional
from sqlalchemy import String, ForeignKey, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class Shop(BaseModel):
    __tablename__ = "shops"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    gst_number: Mapped[Optional[str]] = mapped_column(String(20))
    contact_person: Mapped[Optional[str]] = mapped_column(String(255))
    contact_number: Mapped[Optional[str]] = mapped_column(String(20))
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_ebo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    address: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    district_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("districts.id"), nullable=False, index=True
    )
    taluk_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("taluks.id"), nullable=True, index=True
    )

    district = relationship("District", backref="shops")
    taluk = relationship("Taluk", back_populates="shops")