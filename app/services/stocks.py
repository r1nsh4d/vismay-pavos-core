import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.stock import Stock
from app.schemas.stock import StockUpdate
from fastapi import HTTPException


async def get_stock_by_variant(db: AsyncSession, variant_id: uuid.UUID) -> Stock | None:
    result = await db.execute(select(Stock).where(Stock.variant_id == variant_id))
    return result.scalar_one_or_none()


async def set_stock(db: AsyncSession, variant_id: uuid.UUID, stock_in: StockUpdate) -> Stock:
    stock = await get_stock_by_variant(db, variant_id)
    if not stock:
        stock = Stock(variant_id=variant_id, **stock_in.model_dump())
        db.add(stock)
    else:
        stock.individual_count = stock_in.individual_count
        stock.bundle_count = stock_in.bundle_count
    await db.flush()
    return stock


async def adjust_stock(
    db: AsyncSession,
    variant_id: uuid.UUID,
    individual_delta: int = 0,
    bundle_delta: int = 0,
) -> Stock:
    stock = await get_stock_by_variant(db, variant_id)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock record not found for variant")

    new_individual = stock.individual_count + individual_delta
    new_bundle = stock.bundle_count + bundle_delta

    if new_individual < 0 or new_bundle < 0:
        raise HTTPException(status_code=400, detail="Insufficient stock")

    stock.individual_count = new_individual
    stock.bundle_count = new_bundle
    await db.flush()
    return stock