from sqlalchemy import BigInteger, Boolean, ForeignKey, Text, TIMESTAMP, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[any] = mapped_column(TIMESTAMP, nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="auth_tokens")
