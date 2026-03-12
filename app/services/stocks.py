import uuid
from typing import List, Optional
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.models import Stock, Product, SetType, ProductVariant
from app.models.stock import BundleStock
from app.schemas.stock import BundleStockAdd, IndividualStockAdd


async def get_stock_by_variant(db: AsyncSession, variant_id: uuid.UUID) -> Optional[Stock]:
    return await db.scalar(
        select(Stock)
        .where(Stock.variant_id == variant_id)
        .options(selectinload(Stock.bundle_stocks).selectinload(BundleStock.set_type))
    )

async def get_stock_by_id(db: AsyncSession, stock_id: uuid.UUID) -> Optional[Stock]:
    return await db.scalar(
        select(Stock)
        .where(Stock.id == stock_id)
        .options(
            selectinload(Stock.bundle_stocks).selectinload(BundleStock.set_type)
        )
    )

async def add_individual_stock(db: AsyncSession, data: IndividualStockAdd) -> Stock:
    variant = await db.scalar(select(ProductVariant).where(ProductVariant.id == data.variant_id))
    if not variant:
        raise AppException(status_code=404, detail="Variant not found")

    stock = await _get_or_create_stock(db, data.variant_id)
    stock.individual_count += data.count
    await db.flush()

    # reload with bundle_stocks for response
    return await db.scalar(
        select(Stock)
        .where(Stock.id == stock.id)
        .options(selectinload(Stock.bundle_stocks).selectinload(BundleStock.set_type))
    )


async def _get_or_create_stock(db: AsyncSession, variant_id: uuid.UUID) -> Stock:
    stock = await db.scalar(
        select(Stock)
        .where(Stock.variant_id == variant_id)
        .options(selectinload(Stock.bundle_stocks))
    )
    if not stock:
        stock = Stock(variant_id=variant_id, individual_count=0)
        db.add(stock)
        await db.flush()
    return stock


async def add_bundle_stock(db: AsyncSession, data: BundleStockAdd) -> List[Stock]:
    product = await db.scalar(select(Product).where(Product.id == data.product_id))
    if not product:
        raise AppException(status_code=404, detail="Product not found")

    set_type = await db.scalar(
        select(SetType).where(SetType.id == data.set_type_id).options(selectinload(SetType.items))
    )
    if not set_type:
        raise AppException(status_code=404, detail="SetType not found")
    if not set_type.items:
        raise AppException(status_code=400, detail="SetType has no size items defined")

    variants_result = await db.execute(
        select(ProductVariant).where(ProductVariant.product_id == data.product_id)
    )
    variants = variants_result.scalars().all()
    size_to_variant = {v.size: v for v in variants if v.size}

    missing_sizes = [item.size for item in set_type.items if item.size not in size_to_variant]
    if missing_sizes:
        raise AppException(status_code=400, detail=f"Product has no variants for sizes: {', '.join(missing_sizes)}")

    updated_stocks = []
    for item in set_type.items:
        variant = size_to_variant[item.size]
        stock = await _get_or_create_stock(db, variant.id)

        # Find or create BundleStock for this set_type
        bundle_stock = next(
            (bs for bs in stock.bundle_stocks if bs.set_type_id == data.set_type_id), None
        )
        if not bundle_stock:
            bundle_stock = BundleStock(
                stock_id=stock.id,
                set_type_id=data.set_type_id,
                bundle_count=0,
            )
            db.add(bundle_stock)
            stock.bundle_stocks.append(bundle_stock)

        bundle_stock.bundle_count += data.bundle_count * item.quantity
        updated_stocks.append(stock)

    await db.flush()
    return updated_stocks


async def get_stock_by_set_type(db: AsyncSession, product_id: uuid.UUID, set_type_id: uuid.UUID) -> dict:
    set_type = await db.scalar(
        select(SetType).where(SetType.id == set_type_id).options(selectinload(SetType.items))
    )
    if not set_type:
        raise AppException(status_code=404, detail="SetType not found")

    sizes_in_set = {item.size for item in set_type.items}

    variants_result = await db.execute(
        select(ProductVariant)
        .where(
            ProductVariant.product_id == product_id,
            ProductVariant.size.in_(sizes_in_set),
        )
        .options(
            selectinload(ProductVariant.stock).selectinload(Stock.bundle_stocks)
        )
    )
    variants = variants_result.scalars().all()

    variant_stocks = []
    for v in variants:
        stock = v.stock
        # Only get bundle_count for the specific set_type requested
        bundle_count = 0
        if stock:
            bundle_stock = next(
                (bs for bs in stock.bundle_stocks if bs.set_type_id == set_type_id), None
            )
            bundle_count = bundle_stock.bundle_count if bundle_stock else 0

        variant_stocks.append({
            "variant_id": v.id,
            "size": v.size,
            "color": v.color,
            "sku": v.sku,
            "individual_count": stock.individual_count if stock else 0,
            "bundle_count": bundle_count,
        })

    return {
        "product_id": product_id,
        "set_type_id": set_type_id,
        "set_type_name": set_type.name,
        "variants": variant_stocks,
    }

def serialize_bundle_stock(bs: BundleStock) -> dict:
    return {
        "set_type_id": bs.set_type_id,
        "set_type_name": bs.set_type.name if bs.set_type else None,
        "bundle_count": bs.bundle_count,
    }

def serialize_stock(stock: Stock) -> dict:
    return {
        "id": stock.id,
        "variant_id": stock.variant_id,
        "individual_count": stock.individual_count,
        "bundle_stocks": [serialize_bundle_stock(bs) for bs in stock.bundle_stocks],
    }

