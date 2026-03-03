from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey,
    String, Text, Numeric, UniqueConstraint
)

from sqlalchemy.orm import relationship, DeclarativeBase

from app.models.base import UUIDPrimaryKey, TimestampMixin, Base


# ─── District ─────────────────────────────────────────────────────────────────


class District(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "tb_district"

    name = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)

    user_districts = relationship("UserDistrict", back_populates="district")




