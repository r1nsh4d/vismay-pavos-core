import uuid
from typing import List, Tuple, Optional
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import SetType
from app.models.product import Product, ProductVariant
from app.models.stock import Stock, BundleStock
from app.schemas.product import ProductCreate, ProductUpdate, ProductVariantCreate
from app.services.storage_service import delete_variant_image


def _product_query():
    return select(Product).where(Product.is_deleted == False).options(
        selectinload(Product.model_ref),
        selectinload(Product.variants)
            .selectinload(ProductVariant.stock)
            .selectinload(Stock.bundle_stocks)
            .selectinload(BundleStock.set_type)
            .selectinload(SetType.items),
    )


async def soft_delete_product(db: AsyncSession, product: Product) -> None:
    product.is_deleted = True
    await db.flush()


async def soft_delete_variant(
    db: AsyncSession,
    product_id: uuid.UUID,
    variant_id: uuid.UUID,
) -> bool:
    result = await db.execute(
        select(ProductVariant).where(
            ProductVariant.id == variant_id,
            ProductVariant.product_id == product_id,
        )
    )
    variant = result.scalar_one_or_none()
    if not variant:
        return False

    # Clean up images from OSS before soft-deleting
    await delete_variant_image(variant.image_url, variant.thumbnail_url)

    variant.is_deleted = True
    await db.flush()
    return True


async def create_product(db: AsyncSession, product_in: ProductCreate) -> Product:
    product = Product(
        tenant_id=product_in.tenant_id,
        category_id=product_in.category_id,
        model_id=product_in.model_id,
        name=product_in.name,
        description=product_in.description,
        dp_price=product_in.dp_price,
        mrp=product_in.mrp,
        sell_type=product_in.sell_type,
        is_active=product_in.is_active,
    )
    db.add(product)
    await db.flush()

    for v in product_in.variants:
        variant = ProductVariant(product_id=product.id, **v.model_dump())
        db.add(variant)
        await db.flush()
        db.add(Stock(variant_id=variant.id, individual_count=0))

    await db.flush()
    result = await db.execute(_product_query().where(Product.id == product.id))
    return result.scalar_one()


async def get_product_by_id(db: AsyncSession, product_id: uuid.UUID) -> Product | None:
    result = await db.execute(_product_query().where(Product.id == product_id))
    return result.scalar_one_or_none()


async def search_products(
    db: AsyncSession,
    q: Optional[str] = None,
    tenant_id: Optional[uuid.UUID] = None,
    category_id: Optional[uuid.UUID] = None,
    model_id: Optional[uuid.UUID] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    limit: int = 20,
) -> Tuple[List[Product], int]:
    query = _product_query()

    if q:
        query = query.where(Product.name.ilike(f"%{q}%"))
    if tenant_id:
        query = query.where(Product.tenant_id == tenant_id)
    if category_id:
        query = query.where(Product.category_id == category_id)
    if model_id:
        query = query.where(Product.model_id == model_id)
    if is_active is not None:
        query = query.where(Product.is_active == is_active)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    result = await db.execute(query.offset((page - 1) * limit).limit(limit))
    return result.scalars().all(), total


async def update_product(db: AsyncSession, product: Product, product_in: ProductUpdate) -> Product:
    for field, value in product_in.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    await db.flush()
    result = await db.execute(_product_query().where(Product.id == product.id))
    return result.scalar_one()


async def delete_product(db: AsyncSession, product: Product) -> None:
    await db.delete(product)
    await db.flush()


async def add_variant(db: AsyncSession, product_id: uuid.UUID, variant_in) -> ProductVariant:
    variant = ProductVariant(product_id=product_id, **variant_in.model_dump())
    db.add(variant)
    await db.flush()
    db.add(Stock(variant_id=variant.id, individual_count=0))
    await db.flush()
    return variant


async def update_variant(
    db: AsyncSession, product_id: uuid.UUID, variant_id: uuid.UUID, variant_in) -> Optional[ProductVariant]:
    result = await db.execute(
        select(ProductVariant).where(
            ProductVariant.id == variant_id,
            ProductVariant.product_id == product_id,
        )
    )
    variant = result.scalar_one_or_none()
    if not variant:
        return None

    for field, value in variant_in.model_dump(exclude_unset=True).items():
        setattr(variant, field, value)

    await db.flush()
    return variant


async def delete_variant(
    db: AsyncSession,
    product_id: uuid.UUID,
    variant_id: uuid.UUID,
) -> bool:
    result = await db.execute(
        select(ProductVariant).where(
            ProductVariant.id == variant_id,
            ProductVariant.product_id == product_id,
        )
    )
    variant = result.scalar_one_or_none()
    if not variant:
        return False

    await db.delete(variant)
    await db.flush()
    return True


def serialize_variant_with_stock(v: ProductVariant) -> dict:
    stock = v.stock
    bundle_stocks = []
    if stock and stock.bundle_stocks:
        for bs in stock.bundle_stocks:
            # Find this variant's quantity in the set type
            size_quantity = 1
            if bs.set_type and bs.set_type.items:
                for item in bs.set_type.items:
                    if item.size == v.size:
                        size_quantity = item.quantity
                        break

            bundle_stocks.append({
                "setTypeId": str(bs.set_type_id),
                "setTypeName": bs.set_type.name if bs.set_type else None,
                "bundleCount": bs.bundle_count // size_quantity,  # number of complete sets
                "pieceCount": bs.bundle_count,                    # actual pieces (e.g. M=40)
                "quantityPerSet": size_quantity,                  # e.g. M=2 in BSET
            })

    return {
        "id": str(v.id),
        "color": v.color,
        "pattern": v.pattern,
        "size": v.size,
        "sku": v.sku,
        "imageUrl": v.image_url,
        "thumbnailUrl": v.thumbnail_url,
        "isActive": v.is_active,
        "individualCount": stock.individual_count if stock else 0,
        "bundleStocks": bundle_stocks,
    }


def serialize_product(product: Product) -> dict:
    # Aggregate bundle stocks across all variants grouped by set_type
    set_type_map: dict = {}
    for v in product.variants:
        if v.stock and v.stock.bundle_stocks:
            for bs in v.stock.bundle_stocks:
                key = str(bs.set_type_id)
                if key not in set_type_map:
                    # Find the quantity of this variant's size in the set type
                    size_quantity = 1  # default
                    if bs.set_type and bs.set_type.items:
                        for item in bs.set_type.items:
                            if item.size == v.size:
                                size_quantity = item.quantity
                                break

                    # number of complete sets = bundle_count / size_quantity
                    total_sets = bs.bundle_count // size_quantity

                    set_type_map[key] = {
                        "setTypeId": key,
                        "setTypeName": bs.set_type.name if bs.set_type else None,
                        "totalBundleCount": total_sets,
                    }

    return {
        "id": str(product.id),
        "tenantId": str(product.tenant_id),
        "categoryId": str(product.category_id),
        "modelId": str(product.model_id) if product.model_id else None,
        "modelName": product.model_ref.name if product.model_ref else None,
        "setTypeId": str(product.set_type_id) if product.set_type_id else None,
        "name": product.name,
        "description": product.description,
        "dpPrice": float(product.dp_price),
        "mrp": float(product.mrp),
        "sellType": product.sell_type,
        "isActive": product.is_active,
        # Each variant now includes its own stock counts
        "variants": [
            serialize_variant_with_stock(v)
            for v in product.variants
            if not v.is_deleted  # ← exclude soft-deleted variants
        ],
        # Aggregated bundle stock summary across all variants, grouped by set type
        "bundleStockSummary": list(set_type_map.values()),
        "createdAt": product.created_at.isoformat(),
        "updatedAt": product.updated_at.isoformat(),
    }
