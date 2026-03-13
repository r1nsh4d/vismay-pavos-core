import uuid
from datetime import datetime
from typing import Optional, List, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order, OrderItem, OrderStatus, OrderType
from app.models.product import Product, ProductVariant
from app.models.set_type import SetType, SetTypeItem
from app.models.stock import Stock, BundleStock
from app.schemas.order import OrderCreate, OrderItemCreate, BundleOrderCreate, IndividualOrderCreate
from app.core.exceptions import AppException


async def create_bundle_order(db: AsyncSession, data: BundleOrderCreate, created_by: uuid.UUID) -> Order:
    if not data.items:
        raise AppException(
            status_code=400, detail="Order must have at least one item")

    order_number = await _generate_order_number(db)
    order = Order(
        order_number=order_number,
        tenant_id=data.tenant_id,
        shop_id=data.shop_id,
        distributor_id=data.distributor_id,
        created_by=created_by,
        order_type=OrderType.bundle,
        notes=data.notes,
        status=OrderStatus.placed,
        discount_percent=0,
        subtotal=0,
        discount_amount=0,
        total_amount=0,
        stock_deducted=False,
    )
    db.add(order)
    await db.flush()

    subtotal = 0.0
    for item in data.items:
        product = await db.scalar(select(Product).where(Product.id == item.product_id))
        if not product:
            raise AppException(
                status_code=404, detail=f"Product {item.product_id} not found")

        # Validate set_type exists
        set_type = await db.scalar(select(SetType).where(SetType.id == item.set_type_id))
        if not set_type:
            raise AppException(
                status_code=404, detail=f"SetType {item.set_type_id} not found")

        unit_price = float(product.mrp)
        total_price = unit_price * item.count
        subtotal += total_price

        db.add(OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            set_type_id=item.set_type_id,
            variant_id=None,
            count=item.count,
            unit_price=unit_price,
            total_price=total_price,
        ))

    order.subtotal = subtotal
    order.total_amount = subtotal
    await db.flush()
    return await get_order_by_id(db, order.id)


async def create_individual_order(db: AsyncSession, data: IndividualOrderCreate, created_by: uuid.UUID) -> Order:
    if not data.items:
        raise AppException(
            status_code=400, detail="Order must have at least one item")

    order_number = await _generate_order_number(db)
    order = Order(
        order_number=order_number,
        tenant_id=data.tenant_id,
        shop_id=data.shop_id,
        distributor_id=data.distributor_id,
        created_by=created_by,
        order_type=OrderType.individual,
        notes=data.notes,
        status=OrderStatus.placed,
        discount_percent=0,
        subtotal=0,
        discount_amount=0,
        total_amount=0,
        stock_deducted=False,
    )
    db.add(order)
    await db.flush()

    subtotal = 0.0
    for item in data.items:
        product = await db.scalar(select(Product).where(Product.id == item.product_id))
        if not product:
            raise AppException(
                status_code=404, detail=f"Product {item.product_id} not found")

        # Validate variant belongs to product
        variant = await db.scalar(
            select(ProductVariant).where(
                ProductVariant.id == item.variant_id,
                ProductVariant.product_id == item.product_id,
            )
        )
        if not variant:
            raise AppException(
                status_code=404, detail=f"Variant {item.variant_id} not found for product {item.product_id}")

        unit_price = float(product.mrp)
        total_price = unit_price * item.count
        subtotal += total_price

        db.add(OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            variant_id=item.variant_id,
            set_type_id=None,
            count=item.count,
            unit_price=unit_price,
            total_price=total_price,
        ))

    order.subtotal = subtotal
    order.total_amount = subtotal
    await db.flush()
    return await get_order_by_id(db, order.id)


async def _generate_order_number(db: AsyncSession) -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    prefix = f"ORD-{today}-"
    result = await db.execute(
        select(func.count()).where(Order.order_number.like(f"{prefix}%"))
    )
    count = result.scalar() or 0
    return f"{prefix}{str(count + 1).zfill(4)}"


def _order_query():
    return select(Order).options(
        selectinload(Order.items)
    )


async def get_order_by_id(db: AsyncSession, order_id: uuid.UUID) -> Optional[Order]:
    result = await db.execute(_order_query().where(Order.id == order_id))
    return result.scalar_one_or_none()


async def search_orders(
    db: AsyncSession,
    tenant_id: Optional[uuid.UUID] = None,
    shop_id: Optional[uuid.UUID] = None,
    distributor_id: Optional[uuid.UUID] = None,
    status: Optional[OrderStatus] = None,
    order_type: Optional[OrderType] = None,
    page: int = 1,
    limit: int = 20,
) -> Tuple[List[Order], int]:
    query = _order_query()

    if tenant_id:
        query = query.where(Order.tenant_id == tenant_id)
    if shop_id:
        query = query.where(Order.shop_id == shop_id)
    if distributor_id:
        query = query.where(Order.distributor_id == distributor_id)
    if status:
        query = query.where(Order.status == status)
    if order_type:
        query = query.where(Order.order_type == order_type)

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar() or 0

    result = await db.execute(query.offset((page - 1) * limit).limit(limit).order_by(Order.created_at.desc()))
    return result.scalars().unique().all(), total


async def _resolve_item_price(db: AsyncSession, item: OrderItemCreate, order_type: OrderType) -> float:
    """Get mrp_price from the product."""
    product = await db.scalar(select(Product).where(Product.id == item.product_id))
    if not product:
        raise AppException(
            status_code=404,
            detail=f"Product {item.product_id} not found")
    return float(product.mrp)


async def create_order(db: AsyncSession, data: OrderCreate, created_by: uuid.UUID) -> Order:
    # Validate items
    if not data.items:
        raise AppException(
            status_code=400,
            detail="Order must have at least one item")

    for item in data.items:
        if data.order_type == OrderType.individual and not item.variant_id:
            raise AppException(
                status_code=400,
                detail="Individual orders require variant_id on each item")
        if data.order_type == OrderType.bundle and not item.set_type_id:
            raise AppException(
                status_code=400,
                detail="Bundle orders require set_type_id on each item")

    order_number = await _generate_order_number(db)

    order = Order(
        order_number=order_number,
        tenant_id=data.tenant_id,
        shop_id=data.shop_id,
        distributor_id=data.distributor_id,
        created_by=created_by,
        order_type=data.order_type,
        notes=data.notes,
        status=OrderStatus.placed,
        discount_percent=0,
        subtotal=0,
        discount_amount=0,
        total_amount=0,
        stock_deducted=False,
    )
    db.add(order)
    await db.flush()

    subtotal = 0.0
    for item in data.items:
        unit_price = await _resolve_item_price(db, item, data.order_type)
        total_price = unit_price * item.count
        subtotal += total_price

        order_item = OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            variant_id=item.variant_id,
            set_type_id=item.set_type_id,
            count=item.count,
            unit_price=unit_price,
            total_price=total_price,
        )
        db.add(order_item)

    order.subtotal = subtotal
    order.total_amount = subtotal
    await db.flush()
    return await get_order_by_id(db, order.id)


async def update_status(db: AsyncSession, order: Order, new_status: OrderStatus) -> Order:
    order.status = new_status

    # Auto deduct stock when moving to counting
    if new_status == OrderStatus.counting and not order.stock_deducted:
        await _deduct_stock(db, order)
        order.stock_deducted = True

    await db.flush()
    return await get_order_by_id(db, order.id)


async def apply_discount(db: AsyncSession, order: Order, discount_percent: float) -> Order:
    order.discount_percent = discount_percent
    order.discount_amount = round(float(order.subtotal) * discount_percent / 100, 2)
    order.total_amount = round(float(order.subtotal) - order.discount_amount, 2)
    await db.flush()
    return await get_order_by_id(db, order.id)


async def _deduct_stock(db: AsyncSession, order: Order) -> None:
    # Reload order with items
    result = await db.execute(
        select(Order).where(Order.id == order.id).options(selectinload(Order.items))
    )
    full_order = result.scalar_one()

    for item in full_order.items:
        if full_order.order_type == OrderType.individual:
            # Deduct individual_count from variant's stock
            stock = await db.scalar(
                select(Stock).where(Stock.variant_id == item.variant_id)
            )
            if not stock or stock.individual_count < item.count:
                raise AppException(
                    status_code=400,
                    detail=f"Insufficient individual stock for variant {item.variant_id}"
                )
            stock.individual_count -= item.count

        elif full_order.order_type == OrderType.bundle:
            # Load set_type items
            set_type_items = await db.execute(
                select(SetTypeItem).where(SetTypeItem.set_type_id == item.set_type_id)
            )
            size_items = set_type_items.scalars().all()

            for si in size_items:
                # Find variant by product + size
                variant = await db.scalar(
                    select(ProductVariant).where(
                        ProductVariant.product_id == item.product_id,
                        ProductVariant.size == si.size,
                    )
                )
                if not variant:
                    raise AppException(
                        status_code=400,
                        detail=f"No variant for size {si.size}")

                stock = await db.scalar(
                    select(Stock)
                    .where(Stock.variant_id == variant.id)
                    .options(selectinload(Stock.bundle_stocks))
                )
                bundle_stock = next(
                    (bs for bs in stock.bundle_stocks if bs.set_type_id == item.set_type_id), None
                )
                needed = item.count * si.quantity
                if not bundle_stock or bundle_stock.bundle_count < needed:
                    raise AppException(
                        status_code=400,
                        detail=f"Insufficient bundle stock for size {si.size} in set type {item.set_type_id}"
                    )
                bundle_stock.bundle_count -= needed

    await db.flush()


def serialize_order_item(item: OrderItem) -> dict:
    return {
        "id": str(item.id),
        "product_id": str(item.product_id),
        "variant_id": str(item.variant_id) if item.variant_id else None,
        "set_type_id": str(item.set_type_id) if item.set_type_id else None,
        "count": item.count,
        "unit_price": float(item.unit_price),
        "total_price": float(item.total_price),
    }


def serialize_order(order: Order) -> dict:
    return {
        "id": str(order.id),
        "order_number": order.order_number,
        "tenant_id": str(order.tenant_id),
        "shop_id": str(order.shop_id),
        "distributor_id": str(order.distributor_id) if order.distributor_id else None,
        "created_by": str(order.created_by),
        "order_type": order.order_type,
        "status": order.status,
        "discount_percent": float(order.discount_percent),
        "subtotal": float(order.subtotal),
        "discount_amount": float(order.discount_amount),
        "total_amount": float(order.total_amount),
        "notes": order.notes,
        "stock_deducted": order.stock_deducted,
        "items": [serialize_order_item(i) for i in order.items],
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
    }