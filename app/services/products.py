import uuid
from typing import List, Tuple, Optional
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.product import Product, ProductVariant
from app.models.stock import Stock
from app.schemas.product import ProductCreate, ProductUpdate


def _product_query():
    return select(Product).options(selectinload(Product.variants))


async def get_product_by_id(db: AsyncSession, product_id: uuid.UUID) -> Product | None:
    result = await db.execute(_product_query().where(Product.id == product_id))
    return result.scalar_one_or_none()


async def search_products(
    db: AsyncSession,
    q: Optional[str] = None,
    tenant_id: Optional[uuid.UUID] = None,
    category_id: Optional[uuid.UUID] = None,
    set_type_id: Optional[uuid.UUID] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    limit: int = 20,
) -> Tuple[List[Product], int]:
    query = _product_query()

    if q:
        query = query.where(
            or_(Product.name.ilike(f"%{q}%"), Product.model.ilike(f"%{q}%"))
        )
    if tenant_id:
        query = query.where(Product.tenant_id == tenant_id)
    if category_id:
        query = query.where(Product.category_id == category_id)
    if set_type_id:
        query = query.where(Product.set_type_id == set_type_id)
    if is_active is not None:
        query = query.where(Product.is_active == is_active)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    result = await db.execute(query.offset((page - 1) * limit).limit(limit))
    return result.scalars().all(), total


async def create_product(db: AsyncSession, product_in: ProductCreate) -> Product:
    product = Product(
        tenant_id=product_in.tenant_id,
        category_id=product_in.category_id,
        set_type_id=product_in.set_type_id,
        name=product_in.name,
        model=product_in.model,
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
        # Auto-create stock row for each variant
        db.add(Stock(variant_id=variant.id, individual_count=0, bundle_count=0))

    await db.flush()
    result = await db.execute(_product_query().where(Product.id == product.id))
    return result.scalar_one()


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
    db.add(Stock(variant_id=variant.id, individual_count=0, bundle_count=0))
    await db.flush()
    return variant