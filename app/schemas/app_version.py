from datetime import datetime

from app.schemas.base import CamelModel


class AppVersionOut(CamelModel):
    latest_version: str
    min_supported_version: str
    force_update: bool
    download_url: str
    release_date: datetime
    release_notes: list[str] = []


class VersionCheckIn(CamelModel):
    version: str
