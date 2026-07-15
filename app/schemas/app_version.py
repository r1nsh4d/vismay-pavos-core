from pydantic import Field
from app.schemas.base import CamelModel

class AppVersionOut(CamelModel):
    version_code: int
    version_name: str
    min_required_version_code: int
    apk_url: str
    release_notes: str | None = None

class VersionCheckIn(CamelModel):
    version_code: int

class VersionCheckOut(CamelModel):
    force_update: bool
    latest_version_code: int
    latest_version_name: str
    apk_url: str
    release_notes: str | None = None