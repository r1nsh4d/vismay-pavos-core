import uuid
from typing import List, Optional, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.district import District
from app.schemas.district import DistrictCreate, DistrictUpdate


def serialize_district(d: District) -> dict:
    return {
        "id": str(d.id),
        "name": d.name,
        "state_id": str(d.state_id),
        "state_name": d.state.name if d.state else None,
        "state_code": d.state.code if d.state else None,
        "is_active": d.is_active,
        "created_at": d.created_at.isoformat(),
        "updated_at": d.updated_at.isoformat(),
    }


def _district_query():
    return select(District).options(selectinload(District.state))


async def get_district_by_id(db: AsyncSession, district_id: uuid.UUID) -> Optional[District]:
    result = await db.execute(_district_query().where(District.id == district_id))
    return result.scalar_one_or_none()


async def get_all_districts(
    db: AsyncSession,
    q: Optional[str] = None,
    state_ids: Optional[List[uuid.UUID]] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    limit: int = 20,
) -> Tuple[List[District], int]:
    query = _district_query()

    if q:
        query = query.where(District.name.ilike(f"%{q}%"))
    if state_ids:
        query = query.where(District.state_id.in_(state_ids))
    if is_active is not None:
        query = query.where(District.is_active == is_active)

    query = query.order_by(District.name)

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar_one()

    result = await db.execute(query.offset((page - 1) * limit).limit(limit))
    return result.scalars().all(), total


async def create_district(db: AsyncSession, data: DistrictCreate) -> District:
    district = District(**data.model_dump())
    db.add(district)
    await db.flush()
    return await get_district_by_id(db, district.id)


async def update_district(db: AsyncSession, district: District, data: DistrictUpdate) -> District:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(district, field, value)
    await db.flush()
    return await get_district_by_id(db, district.id)


async def delete_district(db: AsyncSession, district: District) -> None:
    await db.delete(district)
    await db.flush()