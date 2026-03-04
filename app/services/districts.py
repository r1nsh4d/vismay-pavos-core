from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
import uuid

from app.models import District
from app.schemas.district import DistrictCreate


async def get_district_by_id(db: AsyncSession, district_id: uuid.UUID) -> District | None:
    result = await db.execute(select(District).where(District.id == district_id))
    return result.scalar_one_or_none()


async def get_all_districts(
    db: AsyncSession,
    state: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[List[District], int]:
    query = select(District)
    if state:
        query = query.where(District.state.ilike(f"%{state}%"))

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar()

    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    return result.scalars().all(), total


async def create_district(db: AsyncSession, dist_in: DistrictCreate) -> District:
    dist = District(name=dist_in.name, state=dist_in.state)
    db.add(dist)
    await db.flush()
    return dist


async def update_district(db: AsyncSession, dist: District, dist_in: DistrictCreate) -> District:
    dist.name = dist_in.name
    dist.state = dist_in.state
    await db.flush()
    return dist


async def delete_district(db: AsyncSession, dist: District) -> None:
    await db.delete(dist)
    await db.flush()