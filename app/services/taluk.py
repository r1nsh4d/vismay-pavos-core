import uuid
from typing import List, Optional, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import District
from app.models.taluk import Taluk
from app.schemas.taluk import TalukCreate, TalukUpdate


def serialize_taluk(t: Taluk) -> dict:
    return {
        "id": str(t.id),
        "name": t.name,
        "district_id": str(t.district_id),
        "district_name": t.district.name if t.district else None,
        "state_name": t.district.state.name if t.district and t.district.state else None,
        "is_active": t.is_active,
        "created_at": t.created_at.isoformat(),
        "updated_at": t.updated_at.isoformat(),
    }


def _taluk_query():
    return select(Taluk).options(
        selectinload(Taluk.district).selectinload(District.state)
    )


async def get_taluk_by_id(db: AsyncSession, taluk_id: uuid.UUID) -> Optional[Taluk]:
    result = await db.execute(_taluk_query().where(Taluk.id == taluk_id))
    return result.scalar_one_or_none()


async def get_all_taluks(
    db: AsyncSession,
    q: Optional[str] = None,
    district_ids: Optional[List[uuid.UUID]] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    limit: int = 20,
) -> Tuple[List[Taluk], int]:
    query = _taluk_query()

    if q:
        query = query.where(Taluk.name.ilike(f"%{q}%"))
    if district_ids:
        query = query.where(Taluk.district_id.in_(district_ids))
    if is_active is not None:
        query = query.where(Taluk.is_active == is_active)

    query = query.order_by(Taluk.name)

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar_one()

    result = await db.execute(query.offset((page - 1) * limit).limit(limit))
    return result.scalars().all(), total


async def create_taluk(db: AsyncSession, data: TalukCreate) -> Taluk:
    taluk = Taluk(**data.model_dump())
    db.add(taluk)
    await db.flush()
    return await get_taluk_by_id(db, taluk.id)


async def update_taluk(db: AsyncSession, taluk: Taluk, data: TalukUpdate) -> Taluk:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(taluk, field, value)
    await db.flush()
    return await get_taluk_by_id(db, taluk.id)


async def delete_taluk(db: AsyncSession, taluk: Taluk) -> None:
    await db.delete(taluk)
    await db.flush()