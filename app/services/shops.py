import uuid
from fastapi import HTTPException
from typing import List, Tuple, Optional
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import State, Taluk
from app.models.shop import Shop
from app.models.district import District
from app.schemas.shop import ShopCreate, ShopUpdate


def _shop_query():
    return select(Shop).options(
        selectinload(Shop.district).selectinload(District.state),
        selectinload(Shop.taluk),
    )


async def get_shop_by_id(db: AsyncSession, shop_id: uuid.UUID) -> Optional[Shop]:
    result = await db.execute(_shop_query().where(Shop.id == shop_id))
    return result.scalar_one_or_none()


async def search_shops(
    db: AsyncSession,
    q: Optional[str] = None,
    district_ids: List[uuid.UUID] = [],
    taluk_ids: List[uuid.UUID] = [],
    state_ids: List[uuid.UUID] = [],
    is_active: Optional[bool] = None,
    is_ebo: Optional[bool] = None,
    page: int = 1,
    limit: int = 20,
) -> Tuple[List[Shop], int]:
    query = _shop_query()

    if q:
        query = query.where(
            or_(
                Shop.name.ilike(f"%{q}%"),
                Shop.contact_person.ilike(f"%{q}%"),
            )
        )
    if state_ids:
        query = query.join(Shop.district).where(District.state_id.in_(state_ids))
    if district_ids:
        query = query.where(Shop.district_id.in_(district_ids))
    if taluk_ids:
        query = query.where(Shop.taluk_id.in_(taluk_ids))
    if is_active is not None:
        query = query.where(Shop.is_active == is_active)
    if is_ebo is not None:
        query = query.where(Shop.is_ebo == is_ebo)

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar() or 0

    result = await db.execute(query.offset((page - 1) * limit).limit(limit))
    return result.scalars().unique().all(), total


async def _build_address(db: AsyncSession, address: dict) -> dict:
    """Auto-populate state_name and state_code from state_id if not provided."""
    if not address:
        return address

    state_id = address.get("state_id")
    if state_id and not address.get("state_name"):
        state = await db.scalar(
            select(State).where(State.id == uuid.UUID(str(state_id)))
        )
        if state:
            address["state_name"] = state.name
            address["state_code"] = state.code

    if state_id:
        address["state_id"] = str(state_id)

    return address


async def _validate_references(db: AsyncSession, district_id: uuid.UUID, taluk_id: Optional[uuid.UUID]) -> None:
    """Validate district exists and taluk (if provided) belongs to that district."""
    from app.core.exceptions import AppException  # adjust import to your path

    # Validate district
    district = await db.scalar(select(District).where(District.id == district_id))
    if not district:
        raise HTTPException(status_code=404, detail="District not found")

    # Validate taluk belongs to the district
    if taluk_id:
        taluk = await db.scalar(
            select(Taluk).where(Taluk.id == taluk_id, Taluk.district_id == district_id)
        )
        if not taluk:
            raise HTTPException(status_code=400, detail="Taluk does not belong to the given district")


async def create_shop(db: AsyncSession, data: ShopCreate) -> Shop:
    payload = data.model_dump()

    await _validate_references(db, payload["district_id"], payload.get("taluk_id"))

    if payload.get("address"):
        payload["address"] = await _build_address(db, dict(payload["address"]))

    shop = Shop(**payload)
    db.add(shop)
    await db.flush()
    return await get_shop_by_id(db, shop.id)


async def update_shop(db: AsyncSession, shop: Shop, data: ShopUpdate) -> Shop:
    payload = data.model_dump(exclude_unset=True)

    district_id = payload.get("district_id", shop.district_id)
    taluk_id = payload.get("taluk_id", shop.taluk_id)
    if "district_id" in payload or "taluk_id" in payload:
        await _validate_references(db, district_id, taluk_id)

    if "address" in payload and payload["address"] is not None:
        existing = dict(shop.address or {})
        existing.update(payload["address"])
        payload["address"] = await _build_address(db, existing)

    for field, value in payload.items():
        setattr(shop, field, value)

    await db.flush()
    return await get_shop_by_id(db, shop.id)


async def delete_shop(db: AsyncSession, shop: Shop) -> None:
    await db.delete(shop)
    await db.flush()


def serialize_shop(shop: Shop) -> dict:
    return {
        "id": str(shop.id),
        "name": shop.name,
        "gst_number": shop.gst_number,
        "contact_person": shop.contact_person,
        "contact_number": shop.contact_number,
        "phone": shop.phone,
        "address": shop.address or {},
        "is_active": shop.is_active,
        "is_ebo": shop.is_ebo,
        "district_id": str(shop.district_id),
        "district_name": shop.district.name if shop.district else None,
        "state_id": str(shop.district.state_id) if shop.district else None,
        "state_name": shop.district.state.name if shop.district and shop.district.state else None,
        "taluk_id": str(shop.taluk_id) if shop.taluk_id else None,
        "taluk_name": shop.taluk.name if shop.taluk else None,
        "created_at": shop.created_at.isoformat(),
        "updated_at": shop.updated_at.isoformat(),
    }