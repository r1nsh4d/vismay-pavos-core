from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey,
    String, Text, Numeric, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, DeclarativeBase

from app.models.base import utcnow, UUIDPrimaryKey, Base


# ─── Auth Token ───────────────────────────────────────────────────────────────

class AuthToken(UUIDPrimaryKey, Base):
    __tablename__ = "tb_auth_token"

    user_id = Column(UUID(as_uuid=True), ForeignKey("tb_user.id", ondelete="CASCADE"), nullable=False)
    refresh_token = Column(Text, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="tb_auth_token")
