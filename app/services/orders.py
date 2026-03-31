import uuid
from datetime import datetime, date
from typing import Optional, List, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order, OrderItem, OrderStatus, OrderType
from app.models.product import Product, ProductVariant
from app.models.set_type import SetType, SetTypeItem
from app.models.stock import Stock, BundleStock
from app.schemas.order import BundleOrderCreate, IndividualOrderCreate
from app.core.exceptions import AppException


# ── Query helper ───────────────────────────────────────────────────────────────

def _order_query():
    return select(Order).where(Order.is_deleted == False).options(
        selectinload(Order.items),
        selectinload(Order.partial_orders).selectinload(Order.items),
    )


# ── Fetch ──────────────────────────────────────────────────────────────────────

async def get_order_by_id(db: AsyncSession, order_id: uuid.UUID) -> Optional[Order]:
    result = await db.execute(_order_query().where(Order.id == order_id))
    return result.scalar_one_or_none()


async def search_orders(
    db: AsyncSession,
    tenant_id: Optional[uuid.UUID] = None,
    shop_id: Optional[uuid.UUID] = None,
    distributor_id: Optional[uuid.UUID] = None,
    assigned_executive: Optional[uuid.UUID] = None,
    status: Optional[OrderStatus] = None,
    order_type: Optional[OrderType] = None,
    parent_only: bool = True,
    date_from: Optional[date] = None,   # ← new
    date_to: Optional[date] = None,     # ← new
    page: int = 1,
    limit: int = 20,
) -> Tuple[List[Order], int]:
    query = _order_query()

    if parent_only:
        query = query.where(Order.parent_order_id == None)  # noqa
    if tenant_id:
        query = query.where(Order.tenant_id == tenant_id)
    if shop_id:
        query = query.where(Order.shop_id == shop_id)
    if distributor_id:
        query = query.where(Order.distributor_id == distributor_id)
    if assigned_executive:
        query = query.where(Order.assigned_executive == assigned_executive)
    if status:
        query = query.where(Order.status == status)
    if order_type:
        query = query.where(Order.order_type == order_type)
    if date_from:
        query = query.where(Order.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        query = query.where(Order.created_at <= datetime.combine(date_to, datetime.max.time()))

    total = (await db.execute(
        select(func.count()).select_from(query.subquery()))
    ).scalar() or 0

    result = await db.execute(
        query.offset((page - 1) * limit).limit(limit).order_by(Order.created_at.desc())
    )
    return result.scalars().unique().all(), total


# ── Create ─────────────────────────────────────────────────────────────────────

async def _generate_order_number(db: AsyncSession) -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    prefix = f"ORD-{today}-"
    count = (await db.execute(
        select(func.count()).where(Order.order_number.like(f"{prefix}%"))
    )).scalar() or 0
    return f"{prefix}{str(count + 1).zfill(4)}"


async def create_bundle_order(
    db: AsyncSession, data: BundleOrderCreate, created_by: uuid.UUID
) -> Order:
    if not data.items:
        raise AppException(status_code=400, detail="Order must have at least one item")

    order = Order(
        order_number=await _generate_order_number(db),
        tenant_id=data.tenant_id,
        shop_id=data.shop_id,
        created_by=created_by,
        assigned_executive=data.assigned_executive or created_by,
        distributor_id=data.distributor_id,
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
            raise AppException(status_code=404, detail=f"Product {item.product_id} not found")
        set_type = await db.scalar(select(SetType).where(SetType.id == item.set_type_id))
        if not set_type:
            raise AppException(status_code=404, detail=f"SetType {item.set_type_id} not found")

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


async def create_individual_order(
    db: AsyncSession, data: IndividualOrderCreate, created_by: uuid.UUID
) -> Order:
    if not data.items:
        raise AppException(status_code=400, detail="Order must have at least one item")

    order = Order(
        order_number=await _generate_order_number(db),
        tenant_id=data.tenant_id,
        shop_id=data.shop_id,
        created_by=created_by,
        assigned_executive=data.assigned_executive or created_by,
        distributor_id=data.distributor_id,
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
            raise AppException(status_code=404, detail=f"Product {item.product_id} not found")
        variant = await db.scalar(
            select(ProductVariant).where(
                ProductVariant.id == item.variant_id,
                ProductVariant.product_id == item.product_id,
            )
        )
        if not variant:
            raise AppException(
                status_code=404,
                detail=f"Variant {item.variant_id} not found for product {item.product_id}"
            )

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


# ── Status transitions ─────────────────────────────────────────────────────────

async def verify_order(db: AsyncSession, order: Order) -> Order:
    order.status = OrderStatus.verified
    await db.flush()
    return await get_order_by_id(db, order.id)


async def assign_distributor(
    db: AsyncSession, order: Order, distributor_id: uuid.UUID
) -> Order:
    order.distributor_id = distributor_id
    order.status = OrderStatus.assigned
    await db.flush()
    return await get_order_by_id(db, order.id)


async def approve_order(db: AsyncSession, order: Order) -> Order:
    order.status = OrderStatus.approved
    await db.flush()
    return await get_order_by_id(db, order.id)


async def hold_order(db: AsyncSession, order: Order, notes: Optional[str]) -> Order:
    order.status = OrderStatus.on_hold
    if notes:
        order.notes = notes
    await db.flush()
    return await get_order_by_id(db, order.id)


async def reject_order(db: AsyncSession, order: Order, notes: Optional[str]) -> Order:
    order.status = OrderStatus.rejected
    if notes:
        order.notes = notes
    await db.flush()
    return await get_order_by_id(db, order.id)


async def bill_order(db: AsyncSession, order: Order) -> Order:
    order.status = OrderStatus.billed
    await db.flush()
    return await get_order_by_id(db, order.id)


async def move_to_counting(db: AsyncSession, order: Order) -> Order:
    order.status = OrderStatus.counting
    await db.flush()
    return await get_order_by_id(db, order.id)


async def move_to_packing(db: AsyncSession, order: Order) -> Order:
    order.status = OrderStatus.packing
    await db.flush()
    return await get_order_by_id(db, order.id)


async def dispatch_order(
    db: AsyncSession,
    order: Order,
    delivery_partner: str,
    tracking_number: Optional[str],
    delivery_notes: Optional[str],
) -> Order:
    order.status = OrderStatus.dispatched
    order.delivery_partner = delivery_partner
    order.tracking_number = tracking_number
    order.delivery_notes = delivery_notes
    await db.flush()
    return await get_order_by_id(db, order.id)


async def deliver_order(db: AsyncSession, order: Order) -> Order:
    order.status = OrderStatus.delivered
    await db.flush()
    return await get_order_by_id(db, order.id)


async def return_order(db: AsyncSession, order: Order, notes: Optional[str]) -> Order:
    order.status = OrderStatus.returned
    if notes:
        order.notes = notes
    await db.flush()
    return await get_order_by_id(db, order.id)


async def apply_discount(
    db: AsyncSession, order: Order, discount_percent: float
) -> Order:
    order.discount_percent = discount_percent
    order.discount_amount = round(float(order.subtotal) * discount_percent / 100, 2)
    order.total_amount = round(float(order.subtotal) - order.discount_amount, 2)
    await db.flush()
    return await get_order_by_id(db, order.id)


async def soft_delete_order(db: AsyncSession, order: Order) -> None:
    order.is_deleted = True
    await db.flush()


# ── Estimate ───────────────────────────────────────────────────────────────────

async def estimate_order(db: AsyncSession, order: Order) -> Order:
    result = await db.execute(
        select(Order).where(Order.id == order.id).options(selectinload(Order.items))
    )
    full_order = result.scalar_one()
    item_fulfillments = []

    for item in full_order.items:
        if full_order.order_type == OrderType.individual:
            stock = await db.scalar(select(Stock).where(Stock.variant_id == item.variant_id))
            available = stock.individual_count if stock else 0
            fulfill = min(available, item.count)
            item_fulfillments.append({
                "item": item, "fulfill": fulfill, "partial": item.count - fulfill
            })

        elif full_order.order_type == OrderType.bundle:
            size_items = (await db.execute(
                select(SetTypeItem).where(SetTypeItem.set_type_id == item.set_type_id)
            )).scalars().all()

            min_available = None
            for si in size_items:
                variant = await db.scalar(
                    select(ProductVariant).where(
                        ProductVariant.product_id == item.product_id,
                        ProductVariant.size == si.size,
                    )
                )
                if not variant:
                    min_available = 0
                    break

                stock = await db.scalar(
                    select(Stock).where(Stock.variant_id == variant.id)
                    .options(selectinload(Stock.bundle_stocks))
                )
                bundle_stock = next(
                    (bs for bs in stock.bundle_stocks if bs.set_type_id == item.set_type_id), None
                ) if stock else None

                available_bundles = (
                    bundle_stock.bundle_count // si.quantity
                ) if bundle_stock and si.quantity > 0 else 0

                if min_available is None or available_bundles < min_available:
                    min_available = available_bundles

            available = min_available or 0
            fulfill = min(available, item.count)
            item_fulfillments.append({
                "item": item, "fulfill": fulfill, "partial": item.count - fulfill
            })

    has_partial = any(f["partial"] > 0 for f in item_fulfillments)
    has_fulfilled = any(f["fulfill"] > 0 for f in item_fulfillments)

    subtotal = 0.0
    for f in item_fulfillments:
        item = f["item"]
        if f["fulfill"] == 0:
            await db.delete(item)
        else:
            item.count = f["fulfill"]
            item.total_price = float(item.unit_price) * f["fulfill"]
            subtotal += item.total_price
            await _deduct_stock_for_item(db, item, full_order.order_type, f["fulfill"])

    full_order.subtotal = subtotal
    full_order.discount_amount = round(subtotal * float(full_order.discount_percent) / 100, 2)
    full_order.total_amount = round(subtotal - full_order.discount_amount, 2)
    full_order.stock_deducted = has_fulfilled
    full_order.status = OrderStatus.estimated if has_fulfilled else OrderStatus.partial

    if has_partial:
        partial_order = Order(
            order_number=await _generate_order_number(db),
            tenant_id=full_order.tenant_id,
            shop_id=full_order.shop_id,
            created_by=full_order.created_by,
            assigned_executive=full_order.assigned_executive,
            distributor_id=full_order.distributor_id,
            parent_order_id=full_order.id,
            order_type=full_order.order_type,
            status=OrderStatus.approved,
            discount_percent=0,
            subtotal=0, discount_amount=0, total_amount=0,
            stock_deducted=False,
            notes=f"Partial order from {full_order.order_number}",
        )
        db.add(partial_order)
        await db.flush()

        partial_subtotal = 0.0
        for f in item_fulfillments:
            if f["partial"] > 0:
                item = f["item"]
                total_price = float(item.unit_price) * f["partial"]
                partial_subtotal += total_price
                db.add(OrderItem(
                    order_id=partial_order.id,
                    product_id=item.product_id,
                    variant_id=item.variant_id,
                    set_type_id=item.set_type_id,
                    count=f["partial"],
                    unit_price=item.unit_price,
                    total_price=total_price,
                ))

        partial_order.subtotal = partial_subtotal
        partial_order.total_amount = partial_subtotal
        await db.flush()

    await db.flush()
    return await get_order_by_id(db, full_order.id)


async def _deduct_stock_for_item(
    db: AsyncSession, item: OrderItem, order_type: OrderType, count: int
) -> None:
    if order_type == OrderType.individual:
        stock = await db.scalar(select(Stock).where(Stock.variant_id == item.variant_id))
        if stock:
            stock.individual_count -= count

    elif order_type == OrderType.bundle:
        size_items = (await db.execute(
            select(SetTypeItem).where(SetTypeItem.set_type_id == item.set_type_id)
        )).scalars().all()

        for si in size_items:
            variant = await db.scalar(
                select(ProductVariant).where(
                    ProductVariant.product_id == item.product_id,
                    ProductVariant.size == si.size,
                )
            )
            if not variant:
                continue
            stock = await db.scalar(
                select(Stock).where(Stock.variant_id == variant.id)
                .options(selectinload(Stock.bundle_stocks))
            )
            if not stock:
                continue
            bundle_stock = next(
                (bs for bs in stock.bundle_stocks if bs.set_type_id == item.set_type_id), None
            )
            if bundle_stock:
                bundle_stock.bundle_count -= count * si.quantity

    await db.flush()


# ── Serialization ──────────────────────────────────────────────────────────────

def serialize_order_item(item: OrderItem) -> dict:
    return {
        "id": str(item.id),
        "productId": str(item.product_id),
        "variantId": str(item.variant_id) if item.variant_id else None,
        "setTypeId": str(item.set_type_id) if item.set_type_id else None,
        "count": item.count,
        "unitPrice": float(item.unit_price),
        "totalPrice": float(item.total_price),
    }


def serialize_order(order: Order) -> dict:
    return {
        "id": str(order.id),
        "orderNumber": order.order_number,
        "tenantId": str(order.tenant_id),
        "shopId": str(order.shop_id),
        "createdBy": str(order.created_by),
        "assignedExecutive": str(order.assigned_executive) if order.assigned_executive else None,
        "distributorId": str(order.distributor_id) if order.distributor_id else None,
        "parentOrderId": str(order.parent_order_id) if order.parent_order_id else None,
        "orderType": order.order_type,
        "status": order.status,
        "discountPercent": float(order.discount_percent),
        "subtotal": float(order.subtotal),
        "discountAmount": float(order.discount_amount),
        "totalAmount": float(order.total_amount),
        "notes": order.notes,
        "stockDeducted": order.stock_deducted,
        "deliveryPartner": order.delivery_partner,
        "trackingNumber": order.tracking_number,
        "deliveryNotes": order.delivery_notes,
        "items": [serialize_order_item(i) for i in order.items],
        "partialOrders": [
            {
                "id": str(po.id),
                "orderNumber": po.order_number,
                "status": po.status,
                "orderType": po.order_type,
                "subtotal": float(po.subtotal),
                "totalAmount": float(po.total_amount),
                "notes": po.notes,
                "items": [serialize_order_item(i) for i in po.items],
                "createdAt": po.created_at.isoformat(),
                "updatedAt": po.updated_at.isoformat(),
            }
            for po in order.partial_orders
        ],
        "createdAt": order.created_at.isoformat(),
        "updatedAt": order.updated_at.isoformat(),
    }