from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, String, TIMESTAMP, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base, pk_type

if TYPE_CHECKING:
    from app.models.user import UserDistrict
    from app.models.shop import Shop

class District(Base):
    __tablename__ = "districts"

    id: Mapped[int] = mapped_column(pk_type(), primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now())

    # Relationships
    user_districts: Mapped[list["UserDistrict"]] = relationship("UserDistrict", back_populates="district", cascade="all, delete")
    shops: Mapped[list["Shop"]] = relationship("Shop", back_populates="district", cascade="all, delete")
