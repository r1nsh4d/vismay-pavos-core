from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.models.base import BaseModel


# Districts
class District(BaseModel):
    __tablename__ = "districts"
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(255), nullable=False)

    user_districts = relationship("UserDistrict", back_populates="district")