import uuid
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, ForeignKey, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User

class AuthToken(Base):
    __tablename__ = "auth_tokens"

    # Changed from int to uuid.UUID
    # No longer using pk_type() here to ensure explicit UUID control
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    
    # ForeignKey must match the type of User.id
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False
    )
    
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[any] = mapped_column(TIMESTAMP, nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[any] = mapped_column(TIMESTAMP, server_default=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="auth_tokens")