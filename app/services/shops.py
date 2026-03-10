import uuid
from typing import List, Tuple, Optional
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.shop import Shop
from app.schemas.shop import ShopCreate, ShopUpdate, ShopResponse


def _shop_query():
    return select(Shop).options(selectinload(Shop.district))


async def get_shop_by_id(db: AsyncSession, shop_id: uuid.UUID) -> Shop | None:
    result = await db.execute(_shop_query().where(Shop.id == shop_id))
    return result.scalar_one_or_none()


async def search_shops(
    db: AsyncSession,
    q: str | None = None,
    district_ids: List[uuid.UUID] = [],
    state: str | None = None,
    is_active: bool | None = None,
    page: int = 1,
    limit: int = 20,
) -> Tuple[List[Shop], int]:
    query = _shop_query()

    if q:
        query = query.where(
            or_(
                Shop.name.ilike(f"%{q}%"),
                Shop.place.ilike(f"%{q}%"),
                Shop.contact_person.ilike(f"%{q}%"),
            )
        )
    if district_ids:
        query = query.where(Shop.district_id.in_(district_ids))
    if state:
        query = query.where(Shop.state.ilike(f"%{state}%"))
    if is_active is not None:
        query = query.where(Shop.is_active == is_active)

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar() or 0

    result = await db.execute(query.offset((page - 1) * limit).limit(limit))
    return result.scalars().all(), total


async def create_shop(db: AsyncSession, shop_in: ShopCreate) -> Shop:
    shop = Shop(**shop_in.model_dump())
    db.add(shop)
    await db.flush()
    result = await db.execute(_shop_query().where(Shop.id == shop.id))
    return result.scalar_one()


async def update_shop(db: AsyncSession, shop: Shop, shop_in: ShopUpdate) -> Shop:
    for field, value in shop_in.model_dump(exclude_unset=True).items():
        setattr(shop, field, value)
    await db.flush()
    result = await db.execute(_shop_query().where(Shop.id == shop.id))
    return result.scalar_one()


async def delete_shop(db: AsyncSession, shop: Shop) -> None:
    await db.delete(shop)
    await db.flush()


def serialize_shop(shop: Shop) -> ShopResponse:
    return ShopResponse(
        id=shop.id,
        name=shop.name,
        place=shop.place,
        latitude=float(shop.latitude) if shop.latitude is not None else None,
        longitude=float(shop.longitude) if shop.longitude is not None else None,
        gst_number=shop.gst_number,
        contact_person=shop.contact_person,
        contact_number=shop.contact_number,
        phone=shop.phone,
        state=shop.state,
        pincode=shop.pincode,
        is_active=shop.is_active,
        district_id=shop.district_id,
        district_name=shop.district.name if shop.district else None,
        created_at=shop.created_at,
        updated_at=shop.updated_at,
    )