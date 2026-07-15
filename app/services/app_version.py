from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.app_version import AppVersion


async def get_latest_active_version(db: AsyncSession) -> AppVersion | None:
    result = await db.execute(
        select(AppVersion)
        .where(AppVersion.is_active.is_(True))
        .order_by(AppVersion.version_code.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()