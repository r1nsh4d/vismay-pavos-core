import uuid
from typing import Optional, List
from sqlalchemy import String, ForeignKey, Boolean, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel
from app.database import Base


class SetType(BaseModel):
    __tablename__ = "set_types"

    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # ASET, BSET, 4SET
    description: Mapped[Optional[str]] = mapped_column(Text)
    total_pieces: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    category = relationship("Category", back_populates="set_types")
    items = relationship("SetTypeItem", back_populates="set_type", cascade="all, delete-orphan")


class SetTypeItem(Base):
    __tablename__ = "set_type_items"

    set_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("set_types.id"), primary_key=True
    )
    size: Mapped[str] = mapped_column(String(20), primary_key=True)  # M, L, XL, XXL
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    set_type = relationship("SetType", back_populates="items")