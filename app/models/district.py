
import uuid
from typing import TYPE_CHECKING
from sqlalchemy import String, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.user import UserDistrict
    from app.models.shop import Shop

class District(Base):
    __tablename__ = "districts"

    # Primary Key: Switched to UUID with auto-generation
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now())

    # Relationships
    # Ensure UserDistrict and Shop models use UUID for district_id foreign keys
    user_districts: Mapped[list["UserDistrict"]] = relationship(
        "UserDistrict", 
        back_populates="district", 
        cascade="all, delete"
    )
    shops: Mapped[list["Shop"]] = relationship(
        "Shop", 
        back_populates="district", 
        cascade="all, delete"
    )