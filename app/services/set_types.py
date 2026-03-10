import uuid
from typing import List, Tuple
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.set_type import SetType, SetTypeItem
from app.schemas.set_type import SetTypeCreate, SetTypeUpdate


def _set_type_query():
    return select(SetType).options(selectinload(SetType.items))


async def get_set_type_by_id(db: AsyncSession, set_type_id: uuid.UUID) -> SetType | None:
    result = await db.execute(_set_type_query().where(SetType.id == set_type_id))
    return result.scalar_one_or_none()


async def get_all_set_types(
    db: AsyncSession,
    category_id: uuid.UUID | None = None,
    page: int = 1,
    limit: int = 20,
) -> Tuple[List[SetType], int]:
    query = _set_type_query()
    if category_id:
        query = query.where(SetType.category_id == category_id)

    total = (await db.execute(select(func.count()).select_from(
        select(SetType).where(SetType.category_id == category_id).subquery()
        if category_id else select(SetType).subquery()
    ))).scalar() or 0

    result = await db.execute(query.offset((page - 1) * limit).limit(limit))
    return result.scalars().all(), total


async def create_set_type(db: AsyncSession, st_in: SetTypeCreate) -> SetType:
    total_pieces = sum(item.quantity for item in st_in.items)
    st = SetType(
        category_id=st_in.category_id,
        name=st_in.name,
        description=st_in.description,
        total_pieces=total_pieces,
        is_active=st_in.is_active,
    )
    db.add(st)
    await db.flush()

    for item in st_in.items:
        db.add(SetTypeItem(set_type_id=st.id, size=item.size, quantity=item.quantity))
    await db.flush()

    result = await db.execute(_set_type_query().where(SetType.id == st.id))
    return result.scalar_one()


async def update_set_type(db: AsyncSession, st: SetType, st_in: SetTypeUpdate) -> SetType:
    if st_in.name is not None:
        st.name = st_in.name
    if st_in.description is not None:
        st.description = st_in.description
    if st_in.is_active is not None:
        st.is_active = st_in.is_active

    if st_in.items is not None:
        # Replace all items
        await db.execute(delete(SetTypeItem).where(SetTypeItem.set_type_id == st.id))
        for item in st_in.items:
            db.add(SetTypeItem(set_type_id=st.id, size=item.size, quantity=item.quantity))
        st.total_pieces = sum(i.quantity for i in st_in.items)

    await db.flush()
    result = await db.execute(_set_type_query().where(SetType.id == st.id))
    return result.scalar_one()


async def delete_set_type(db: AsyncSession, st: SetType) -> None:
    await db.delete(st)
    await db.flush()