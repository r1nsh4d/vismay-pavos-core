from sqlalchemy import Integer, String, Boolean, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class AppVersion(Base):
    __tablename__ = "app_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_code: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)  # e.g. 42, always increasing
    version_name: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "2.4.1"
    min_required_version_code: Mapped[int] = mapped_column(Integer, nullable=False)  # force-update threshold
    apk_key: Mapped[str] = mapped_column(String(255), nullable=False)  # object storage key
    apk_url: Mapped[str] = mapped_column(String(500), nullable=False)  # public/download URL
    release_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())