import uuid
from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class District(BaseModel):
    __tablename__ = "districts"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    state_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("states.id"), nullable=False, index=True
    )

    state = relationship("State", back_populates="districts")
    taluks = relationship("Taluk", back_populates="district")
    user_districts = relationship("UserDistrict", back_populates="district")