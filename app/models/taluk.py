import uuid
from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class Taluk(BaseModel):
    __tablename__ = "taluks"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    district_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("districts.id"), nullable=False, index=True
    )

    district = relationship("District", back_populates="taluks")
    shops = relationship("Shop", back_populates="taluk")