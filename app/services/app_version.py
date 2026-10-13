from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.app_version import AppVersion


async def get_latest_active_version(db: AsyncSession) -> AppVersion | None:
    """Most recently released active version. Ordered by release time (the model uses a
    string `version`, not an integer version_code), matching the /app-version router."""
    result = await db.execute(
        select(AppVersion)
        .where(AppVersion.is_active.is_(True))
        .order_by(AppVersion.created_at.desc(), AppVersion.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()