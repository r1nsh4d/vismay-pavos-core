from sqlalchemy import BigInteger, String, TIMESTAMP, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class District(Base):
    __tablename__ = "districts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now())

    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="district")
