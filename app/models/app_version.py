from datetime import datetime

from sqlalchemy import Integer, String, Boolean, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class AppVersion(Base):
    __tablename__ = "app_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)          # e.g. "2.3.0"
    min_supported_version: Mapped[str] = mapped_column(String(20), nullable=False)         # e.g. "2.1.0"
    force_update: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)      # mandatory update flag
    apk_key: Mapped[str] = mapped_column(String(255), nullable=False)                       # object storage key
    apk_url: Mapped[str] = mapped_column(String(500), nullable=False)                       # download URL
    release_notes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)    # list of bullet points
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())  # release date
