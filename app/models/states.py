from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class State(BaseModel):
    __tablename__ = "states"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)  # e.g. "KL", "TN", "MH"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    districts = relationship("District", back_populates="state")