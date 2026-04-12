import uuid
from datetime import datetime, date, timezone
from typing import Optional, List, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import (
    Order, OrderItem, OrderReturn, OrderStatus, OrderType,
    ReturnType, PriceType, CANCELLABLE_STATUSES, STOCK_RESTORE_STATUSES,
)
from app.models.product import Product, ProductVariant
from app.models.set_type import SetType, SetTypeItem
from app.models.stock import Stock, BundleStock
from app.schemas.order import (
    BundleOrderCreate, IndividualOrderCreate,
    SplitOrderInput, CreateOrderReturnInput,
)
from app.core.exceptions import AppException


# ── Helpers ────────────────────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc)


def _stamp(order: Order, status: OrderStatus) -> None:
    mapping = {
        OrderStatus.placed: "placed_at",
        OrderStatus.verified: "verified_at",
        OrderStatus.assigned: "assigned_at",
        OrderStatus.approved: "approved_at",
        OrderStatus.estimated: "estimated_at",
        OrderStatus.billed: "billed_at",
        OrderStatus.packing: "packing_at",
        OrderStatus.dispatched: "dispatched_at",
        OrderStatus.delivered: "delivered_at",
        OrderStatus.cancelled: "cancelled_at",
        OrderStatus.rejected: "rejected_at",
        OrderStatus.returned: "returned_at",
    }
    field = mapping.get(status)
    if field and not getattr(order, field):
        setattr(order, field, _now())


def _user_full_name(user) -> Optional[str]:
    if not user:
        return None
    return f"{user.first_name} {user.last_name}".strip() if user.last_name else user.first_name


def _get_unit_price(product: Product, price_type: PriceType) -> float:
    if price_type == PriceType.dp:
        return float(product.dp_price)
    return float(product.mrp)


def _recalculate_totals(order: Order, items=None) -> None:
    source = items if items is not None else order.items
    subtotal = sum(float(i.total_price) for i in source)
    percent_discount = round(subtotal * float(order.discount_percent) / 100, 2)
    flat_discount = float(order.discount_flat)
    discount_amount = round(min(percent_discount + flat_discount, subtotal), 2)
    order.subtotal = subtotal
    order.discount_amount = discount_amount
    order.total_amount = round(subtotal - discount_amount, 2)


# ── Queries ────────────────────────────────────────────────────────────────────

def _order_list_query():
    return (
        select(Order)
        .where(Order.is_deleted == False)  # noqa
        .options(
            selectinload(Order.items).selectinload(OrderItem.product),
            selectinload(Order.items).selectinload(OrderItem.variant),
            selectinload(Order.items).selectinload(OrderItem.set_type),
            selectinload(Order.shop),
            selectinload(Order.creator),
            selectinload(Order.executive),
            selectinload(Order.distributor),
            selectinload(Order.tenant),
        )
    )


def _order_detail_query():
    return (
        select(Order)
        .where(Order.is_deleted == False)  # noqa
        .options(
            selectinload(Order.items).selectinload(OrderItem.product),
            selectinload(Order.items).selectinload(OrderItem.variant),
            selectinload(Order.items).selectinload(OrderItem.set_type),
            selectinload(Order.items).selectinload(OrderItem.item_returns),
            selectinload(Order.child_orders).selectinload(Order.items).selectinload(OrderItem.product),
            selectinload(Order.child_orders).selectinload(Order.items).selectinload(OrderItem.variant),
            selectinload(Order.child_orders).selectinload(Order.items).selectinload(OrderItem.set_type),
            selectinload(Order.child_orders).selectinload(Order.items).selectinload(OrderItem.item_returns),
            selectinload(Order.order_returns).selectinload(OrderReturn.product),
            selectinload(Order.order_returns).selectinload(OrderReturn.variant),
            selectinload(Order.order_returns).selectinload(OrderReturn.set_type),
            selectinload(Order.order_returns).selectinload(OrderReturn.processor),
            selectinload(Order.shop),
            selectinload(Order.creator),
            selectinload(Order.executive),
            selectinload(Order.distributor),
            selectinload(Order.tenant),
        )
    )


# ── Fetch ──────────────────────────────────────────────────────────────────────

async def get_order_by_id(db: AsyncSession, order_id: uuid.UUID) -> Optional[Order]:
    result = await db.execute(_order_detail_query().where(Order.id == order_id))
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
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    page: int = 1,
    limit: int = 20,
) -> Tuple[List[Order], int]:
    filters = [Order.is_deleted == False]  # noqa

    if parent_only:
        filters.append(Order.parent_order_id == None)  # noqa
    if tenant_id:
        filters.append(Order.tenant_id == tenant_id)
    if shop_id:
        filters.append(Order.shop_id == shop_id)
    if distributor_id:
        filters.append(Order.distributor_id == distributor_id)
    if assigned_executive:
        filters.append(Order.assigned_executive == assigned_executive)
    if status:
        filters.append(Order.status == status)
    if order_type:
        filters.append(Order.order_type == order_type)
    if date_from:
        filters.append(Order.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        filters.append(Order.created_at <= datetime.combine(date_to, datetime.max.time()))

    total = (await db.execute(
        select(func.count(Order.id)).where(*filters)
    )).scalar() or 0

    result = await db.execute(
        _order_list_query()
        .where(*filters)
        .offset((page - 1) * limit)
        .limit(limit)
        .order_by(Order.created_at.desc())
    )
    return result.scalars().unique().all(), total


# ── Order number ───────────────────────────────────────────────────────────────

async def _generate_order_number(db: AsyncSession) -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    prefix = f"ORD-{today}-"
    count = (await db.execute(
        select(func.count()).where(Order.order_number.like(f"{prefix}%"))
    )).scalar() or 0
    return f"{prefix}{str(count + 1).zfill(4)}"


# ── Stock helpers ──────────────────────────────────────────────────────────────

async def _get_available_individual(db: AsyncSession, variant_id: uuid.UUID) -> int:
    stock = await db.scalar(select(Stock).where(Stock.variant_id == variant_id))
    return int(stock.individual_count) if stock else 0


async def _get_available_bundle(
    db: AsyncSession, product_id: uuid.UUID, set_type_id: uuid.UUID
) -> int:
    size_items = (await db.execute(
        select(SetTypeItem).where(SetTypeItem.set_type_id == set_type_id)
    )).scalars().all()

    if not size_items:
        return 0

    min_available = None
    for si in size_items:
        variant = await db.scalar(
            select(ProductVariant).where(
                ProductVariant.product_id == product_id,
                ProductVariant.size == si.size,
            )
        )
        if not variant:
            return 0
        stock = await db.scalar(
            select(Stock).where(Stock.variant_id == variant.id)
            .options(selectinload(Stock.bundle_stocks))
        )
        bundle_stock = next(
            (bs for bs in stock.bundle_stocks if bs.set_type_id == set_type_id), None
        ) if stock else None
        available = (
            bundle_stock.bundle_count // si.quantity
        ) if bundle_stock and si.quantity > 0 else 0
        if min_available is None or available < min_available:
            min_available = available

    return min_available or 0


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


async def _restore_stock_for_item(
    db: AsyncSession, item: OrderItem, order_type: OrderType, count: int
) -> None:
    if order_type == OrderType.individual:
        stock = await db.scalar(select(Stock).where(Stock.variant_id == item.variant_id))
        if stock:
            stock.individual_count += count
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
                bundle_stock.bundle_count += count * si.quantity
    await db.flush()


async def _restore_all_stock(db: AsyncSession, order: Order) -> None:
    for item in order.items:
        await _restore_stock_for_item(db, item, order.order_type, item.count)


# ── Create ─────────────────────────────────────────────────────────────────────

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
        price_type=data.price_type,
        notes=data.notes,
        status=OrderStatus.placed,
        discount_percent=0,
        discount_flat=0,
        subtotal=0,
        discount_amount=0,
        total_amount=0,
        stock_deducted=False,
        placed_at=_now(),
    )
    db.add(order)
    await db.flush()

    order_items = []
    for item in data.items:
        product = await db.scalar(select(Product).where(Product.id == item.product_id))
        if not product:
            raise AppException(status_code=404, detail=f"Product {item.product_id} not found")
        set_type = await db.scalar(select(SetType).where(SetType.id == item.set_type_id))
        if not set_type:
            raise AppException(status_code=404, detail=f"SetType {item.set_type_id} not found")

        unit_price = _get_unit_price(product, data.price_type)
        oi = OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            set_type_id=item.set_type_id,
            variant_id=None,
            count=item.count,
            unit_price=unit_price,
            total_price=unit_price * item.count,
        )
        db.add(oi)
        order_items.append(oi)

    await db.flush()
    _recalculate_totals(order, items=order_items)

    for oi in order_items:
        await _deduct_stock_for_item(db, oi, OrderType.bundle, oi.count)

    order.stock_deducted = True
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
        price_type=data.price_type,
        notes=data.notes,
        status=OrderStatus.placed,
        discount_percent=0,
        discount_flat=0,
        subtotal=0,
        discount_amount=0,
        total_amount=0,
        stock_deducted=False,
        placed_at=_now(),
    )
    db.add(order)
    await db.flush()

    order_items = []
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

        unit_price = _get_unit_price(product, data.price_type)
        oi = OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            variant_id=item.variant_id,
            set_type_id=None,
            count=item.count,
            unit_price=unit_price,
            total_price=unit_price * item.count,
        )
        db.add(oi)
        order_items.append(oi)

    await db.flush()
    _recalculate_totals(order, items=order_items)

    for oi in order_items:
        await _deduct_stock_for_item(db, oi, OrderType.individual, oi.count)

    order.stock_deducted = True
    await db.flush()
    return await get_order_by_id(db, order.id)


# ── Edit item at pre-bill stage ────────────────────────────────────────────────

async def update_order_item(
    db: AsyncSession,
    order: Order,
    order_item_id: uuid.UUID,
    new_count: int,
) -> Order:
    item = next((i for i in order.items if i.id == order_item_id), None)
    if not item:
        raise AppException(status_code=404, detail="Order item not found")
    if new_count <= 0:
        raise AppException(status_code=400, detail="Count must be greater than 0")

    old_count = item.count
    diff = new_count - old_count

    if diff > 0:
        if order.order_type == OrderType.individual:
            available = await _get_available_individual(db, item.variant_id)
            if available < diff:
                raise AppException(
                    status_code=400,
                    detail=f"Only {available} units available, cannot increase by {diff}"
                )
        else:
            available = await _get_available_bundle(db, item.product_id, item.set_type_id)
            if available < diff:
                raise AppException(
                    status_code=400,
                    detail=f"Only {available} bundles available, cannot increase by {diff}"
                )
        await _deduct_stock_for_item(db, item, order.order_type, diff)
    elif diff < 0:
        await _restore_stock_for_item(db, item, order.order_type, abs(diff))

    item.count = new_count
    item.total_price = float(item.unit_price) * new_count
    _recalculate_totals(order)
    await db.flush()
    return await get_order_by_id(db, order.id)


# ── Estimate split preview ─────────────────────────────────────────────────────

async def get_estimate_split_preview(db: AsyncSession, order: Order) -> dict:
    shortfall_items = []
    fully_available_items = []

    for item in order.items:
        if order.order_type == OrderType.individual:
            available_now = await _get_available_individual(db, item.variant_id)
        else:
            available_now = await _get_available_bundle(db, item.product_id, item.set_type_id)

        available_at_placement = available_now + item.count
        coverable = min(item.count, max(0, available_at_placement))
        shortfall = item.count - coverable

        item_data = {
            "orderItemId": str(item.id),
            "productId": str(item.product_id),
            "productName": item.product.name if item.product else None,
            "variantId": str(item.variant_id) if item.variant_id else None,
            "variantSize": item.variant.size if item.variant else None,
            "variantColor": item.variant.color if item.variant else None,
            "setTypeId": str(item.set_type_id) if item.set_type_id else None,
            "setTypeName": item.set_type.name if item.set_type else None,
            "requested": item.count,
            "available": coverable,
            "shortfall": shortfall,
        }

        if shortfall > 0:
            shortfall_items.append(item_data)
        else:
            fully_available_items.append(serialize_order_item(item))

    return {
        "hasShortfall": len(shortfall_items) > 0,
        "shortfallItems": shortfall_items,
        "fullyAvailableItems": fully_available_items,
    }


# ── Split ──────────────────────────────────────────────────────────────────────

async def split_order(
    db: AsyncSession,
    order: Order,
    split_input: SplitOrderInput,
    created_by: uuid.UUID,
) -> Order:
    parent_items_by_id = {item.id: item for item in order.items}
    validated = []

    for si in split_input.items:
        parent_item = parent_items_by_id.get(si.order_item_id)
        if not parent_item:
            raise AppException(
                status_code=404,
                detail=f"OrderItem {si.order_item_id} not found in order {order.order_number}"
            )
        if si.count <= 0:
            raise AppException(status_code=400, detail="Split count must be greater than 0")
        if si.count > parent_item.count:
            raise AppException(
                status_code=400,
                detail=f"Split count {si.count} exceeds item count {parent_item.count}"
            )
        validated.append({"parent_item": parent_item, "split_count": si.count})

    new_order = Order(
        order_number=await _generate_order_number(db),
        tenant_id=order.tenant_id,
        shop_id=order.shop_id,
        created_by=created_by,
        assigned_executive=order.assigned_executive,
        distributor_id=order.distributor_id,
        parent_order_id=order.id if split_input.create_as == "child" else None,
        order_type=order.order_type,
        price_type=order.price_type,
        status=OrderStatus.approved,
        placed_at=_now(),
        discount_percent=0,
        discount_flat=0,
        subtotal=0,
        discount_amount=0,
        total_amount=0,
        stock_deducted=True,
        notes=split_input.notes or f"Split from {order.order_number}",
    )
    db.add(new_order)
    await db.flush()

    for v in validated:
        parent_item = v["parent_item"]
        split_count = v["split_count"]
        remaining = parent_item.count - split_count

        db.add(OrderItem(
            order_id=new_order.id,
            product_id=parent_item.product_id,
            variant_id=parent_item.variant_id,
            set_type_id=parent_item.set_type_id,
            count=split_count,
            unit_price=parent_item.unit_price,
            total_price=float(parent_item.unit_price) * split_count,
        ))

        if remaining == 0:
            await db.delete(parent_item)
        else:
            parent_item.count = remaining
            parent_item.total_price = float(parent_item.unit_price) * remaining

    await db.flush()

    parent_result = await db.execute(
        select(Order).where(Order.id == order.id).options(selectinload(Order.items))
    )
    refreshed_parent = parent_result.scalar_one()
    _recalculate_totals(refreshed_parent)

    new_result = await db.execute(
        select(Order).where(Order.id == new_order.id).options(selectinload(Order.items))
    )
    refreshed_new = new_result.scalar_one()
    _recalculate_totals(refreshed_new)

    await db.flush()
    return await get_order_by_id(db, new_order.id)


# ── Status transitions ─────────────────────────────────────────────────────────

async def verify_order(db: AsyncSession, order: Order, notes: Optional[str]) -> Order:
    order.status = OrderStatus.verified
    _stamp(order, OrderStatus.verified)
    if notes:
        order.notes = notes
    await db.flush()
    return await get_order_by_id(db, order.id)


async def assign_distributor(
    db: AsyncSession, order: Order, distributor_id: uuid.UUID, notes: Optional[str]
) -> Order:
    order.distributor_id = distributor_id
    order.status = OrderStatus.assigned
    _stamp(order, OrderStatus.assigned)
    if notes:
        order.notes = notes
    await db.flush()
    return await get_order_by_id(db, order.id)


async def approve_order(db: AsyncSession, order: Order, notes: Optional[str]) -> Order:
    order.status = OrderStatus.approved
    _stamp(order, OrderStatus.approved)
    if notes:
        order.notes = notes
    await db.flush()
    return await get_order_by_id(db, order.id)


async def hold_order(db: AsyncSession, order: Order, notes: Optional[str]) -> Order:
    order.status = OrderStatus.on_hold
    if notes:
        order.notes = notes
    await db.flush()
    return await get_order_by_id(db, order.id)


async def unhold_order(db: AsyncSession, order: Order, notes: Optional[str]) -> Order:
    order.status = OrderStatus.assigned
    if notes:
        order.notes = notes
    await db.flush()
    return await get_order_by_id(db, order.id)


async def reject_order(db: AsyncSession, order: Order, notes: Optional[str]) -> Order:
    if order.stock_deducted:
        await _restore_all_stock(db, order)
        order.stock_deducted = False
    order.status = OrderStatus.rejected
    _stamp(order, OrderStatus.rejected)
    if notes:
        order.notes = notes
    await db.flush()
    return await get_order_by_id(db, order.id)


async def cancel_order(db: AsyncSession, order: Order, notes: Optional[str]) -> Order:
    if order.status not in CANCELLABLE_STATUSES:
        raise AppException(
            status_code=400,
            detail=f"Order in status '{order.status}' cannot be cancelled"
        )
    if order.stock_deducted:
        await _restore_all_stock(db, order)
        order.stock_deducted = False
    order.status = OrderStatus.cancelled
    _stamp(order, OrderStatus.cancelled)
    if notes:
        order.notes = notes
    await db.flush()
    return await get_order_by_id(db, order.id)


async def estimate_order(db: AsyncSession, order: Order, notes: Optional[str]) -> Order:
    _recalculate_totals(order)
    order.status = OrderStatus.estimated
    _stamp(order, OrderStatus.estimated)
    if notes:
        order.notes = notes
    await db.flush()
    return await get_order_by_id(db, order.id)


async def bill_order(db: AsyncSession, order: Order, notes: Optional[str]) -> Order:
    order.status = OrderStatus.billed
    _stamp(order, OrderStatus.billed)
    if notes:
        order.notes = notes
    await db.flush()
    return await get_order_by_id(db, order.id)


async def apply_discount(
    db: AsyncSession,
    order: Order,
    discount_percent: Optional[float],
    discount_flat: Optional[float],
    notes: Optional[str],
) -> Order:
    if discount_percent is not None:
        if not (0 <= discount_percent <= 100):
            raise AppException(status_code=400, detail="discount_percent must be between 0 and 100")
        order.discount_percent = discount_percent
    if discount_flat is not None:
        if discount_flat < 0:
            raise AppException(status_code=400, detail="discount_flat must be >= 0")
        order.discount_flat = discount_flat
    if notes:
        order.notes = notes
    _recalculate_totals(order)
    await db.flush()
    return await get_order_by_id(db, order.id)


async def move_to_packing(db: AsyncSession, order: Order, notes: Optional[str]) -> Order:
    order.status = OrderStatus.packing
    _stamp(order, OrderStatus.packing)
    if notes:
        order.notes = notes
    await db.flush()
    return await get_order_by_id(db, order.id)


async def dispatch_order(
    db: AsyncSession,
    order: Order,
    delivery_partner: str,
    tracking_number: Optional[str],
    tracking_link: Optional[str],
    delivery_notes: Optional[str],
    notes: Optional[str],
) -> Order:
    order.status = OrderStatus.dispatched
    _stamp(order, OrderStatus.dispatched)
    order.delivery_partner = delivery_partner
    order.tracking_number = tracking_number
    order.tracking_link = tracking_link
    order.delivery_notes = delivery_notes
    if notes:
        order.notes = notes
    await db.flush()
    return await get_order_by_id(db, order.id)


async def deliver_order(db: AsyncSession, order: Order, notes: Optional[str]) -> Order:
    order.status = OrderStatus.delivered
    _stamp(order, OrderStatus.delivered)
    if notes:
        order.notes = notes
    await db.flush()
    return await get_order_by_id(db, order.id)


async def update_delivered_at(
    db: AsyncSession, order: Order, delivered_at: datetime, notes: Optional[str]
) -> Order:
    order.delivered_at = delivered_at
    if notes:
        order.notes = notes
    await db.flush()
    return await get_order_by_id(db, order.id)


async def soft_delete_order(db: AsyncSession, order: Order) -> None:
    order.is_deleted = True
    await db.flush()


# ── Returns ────────────────────────────────────────────────────────────────────

async def process_return(
    db: AsyncSession,
    order: Order,
    return_input: CreateOrderReturnInput,
    processed_by: uuid.UUID,
) -> List[OrderReturn]:
    order_items_by_id = {item.id: item for item in order.items}
    created_returns = []

    for ri in return_input.items:
        order_item = order_items_by_id.get(ri.order_item_id)
        if not order_item:
            raise AppException(
                status_code=404,
                detail=f"OrderItem {ri.order_item_id} not found in order"
            )
        if ri.count <= 0:
            raise AppException(status_code=400, detail="Return count must be greater than 0")

        already_returned = (await db.execute(
            select(func.coalesce(func.sum(OrderReturn.count), 0)).where(
                OrderReturn.order_item_id == ri.order_item_id,
                OrderReturn.order_id == order.id,
            )
        )).scalar() or 0

        if already_returned + ri.count > order_item.count:
            raise AppException(
                status_code=400,
                detail=f"Total returned ({already_returned + ri.count}) exceeds "
                       f"original count ({order_item.count}) for item {ri.order_item_id}"
            )

        await _restore_stock_by_return_type(db, order_item, ri.return_type, ri.count)

        order_return = OrderReturn(
            order_id=order.id,
            order_item_id=order_item.id,
            product_id=order_item.product_id,
            variant_id=order_item.variant_id,
            set_type_id=order_item.set_type_id,
            return_type=ri.return_type,
            count=ri.count,
            processed_by=processed_by,
            notes=ri.notes or return_input.notes,
        )
        db.add(order_return)
        created_returns.append(order_return)

    await db.flush()
    await _update_order_return_status(db, order)
    await db.flush()
    return created_returns


async def _restore_stock_by_return_type(
    db: AsyncSession,
    order_item: OrderItem,
    return_type: ReturnType,
    count: int,
) -> None:
    if return_type == ReturnType.individual:
        if order_item.variant_id:
            stock = await db.scalar(
                select(Stock).where(Stock.variant_id == order_item.variant_id)
            )
            if stock:
                stock.individual_count += count
        else:
            size_items = (await db.execute(
                select(SetTypeItem).where(SetTypeItem.set_type_id == order_item.set_type_id)
            )).scalars().all()
            for si in size_items:
                variant = await db.scalar(
                    select(ProductVariant).where(
                        ProductVariant.product_id == order_item.product_id,
                        ProductVariant.size == si.size,
                    )
                )
                if not variant:
                    continue
                stock = await db.scalar(
                    select(Stock).where(Stock.variant_id == variant.id)
                )
                if stock:
                    stock.individual_count += count * si.quantity

    elif return_type == ReturnType.bundle:
        size_items = (await db.execute(
            select(SetTypeItem).where(SetTypeItem.set_type_id == order_item.set_type_id)
        )).scalars().all()
        for si in size_items:
            variant = await db.scalar(
                select(ProductVariant).where(
                    ProductVariant.product_id == order_item.product_id,
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
                (bs for bs in stock.bundle_stocks
                 if bs.set_type_id == order_item.set_type_id), None
            )
            if bundle_stock:
                bundle_stock.bundle_count += count * si.quantity

    await db.flush()


async def _update_order_return_status(db: AsyncSession, order: Order) -> None:
    total_ordered = sum(item.count for item in order.items)
    total_returned = (await db.execute(
        select(func.coalesce(func.sum(OrderReturn.count), 0)).where(
            OrderReturn.order_id == order.id
        )
    )).scalar() or 0

    if total_returned <= 0:
        return
    elif total_returned >= total_ordered:
        order.status = OrderStatus.returned
        _stamp(order, OrderStatus.returned)
        order.stock_deducted = False
    else:
        order.status = OrderStatus.partially_returned


async def get_returns_for_order(
    db: AsyncSession, order_id: uuid.UUID
) -> List[OrderReturn]:
    result = await db.execute(
        select(OrderReturn)
        .where(OrderReturn.order_id == order_id)
        .options(
            selectinload(OrderReturn.product),
            selectinload(OrderReturn.variant),
            selectinload(OrderReturn.set_type),
            selectinload(OrderReturn.processor),
        )
        .order_by(OrderReturn.created_at.desc())
    )
    return result.scalars().all()


# ── Serialization ──────────────────────────────────────────────────────────────

def _ts(val) -> Optional[str]:
    return val.isoformat() if val else None


def serialize_order_item(item: OrderItem) -> dict:
    total_returned = sum(r.count for r in item.item_returns) if hasattr(item, "item_returns") and item.item_returns else 0
    return {
        "id": str(item.id),
        "productId": str(item.product_id),
        "productName": item.product.name if item.product else None,
        "productMrp": float(item.product.mrp) if item.product else None,
        "productDpPrice": float(item.product.dp_price) if item.product else None,
        "variantId": str(item.variant_id) if item.variant_id else None,
        "variantSku": item.variant.sku if item.variant else None,
        "variantSize": item.variant.size if item.variant else None,
        "variantColor": item.variant.color if item.variant else None,
        "variantPattern": item.variant.pattern if item.variant else None,
        "variantThumbnailUrl": item.variant.thumbnail_url if item.variant else None,
        "setTypeId": str(item.set_type_id) if item.set_type_id else None,
        "setTypeName": item.set_type.name if item.set_type else None,
        "count": item.count,
        "returnedCount": total_returned,
        "remainingCount": item.count - total_returned,
        "unitPrice": float(item.unit_price),
        "totalPrice": float(item.total_price),
    }


def serialize_order_return(r: OrderReturn) -> dict:
    processor = r.processor
    processor_name = None
    if processor:
        processor_name = (
            f"{processor.first_name} {processor.last_name}".strip()
            if processor.last_name else processor.first_name
        )
    return {
        "id": str(r.id),
        "orderId": str(r.order_id),
        "orderItemId": str(r.order_item_id),
        "productId": str(r.product_id),
        "productName": r.product.name if r.product else None,
        "variantId": str(r.variant_id) if r.variant_id else None,
        "variantSize": r.variant.size if r.variant else None,
        "variantColor": r.variant.color if r.variant else None,
        "variantPattern": r.variant.pattern if r.variant else None,
        "setTypeId": str(r.set_type_id) if r.set_type_id else None,
        "setTypeName": r.set_type.name if r.set_type else None,
        "returnType": r.return_type,
        "count": r.count,
        "processedBy": str(r.processed_by),
        "processedByName": processor_name,
        "notes": r.notes,
        "createdAt": r.created_at.isoformat(),
    }


def serialize_order_list(order: Order) -> dict:
    return {
        "id": str(order.id),
        "orderNumber": order.order_number,
        "tenantId": str(order.tenant_id),
        "tenantName": order.tenant.name if order.tenant else None,
        "shopId": str(order.shop_id),
        "shopName": order.shop.name if order.shop else None,
        "shopPhone": order.shop.phone if order.shop else None,
        "createdBy": str(order.created_by),
        "createdByName": _user_full_name(order.creator),
        "assignedExecutive": str(order.assigned_executive) if order.assigned_executive else None,
        "assignedExecutiveName": _user_full_name(order.executive),
        "distributorId": str(order.distributor_id) if order.distributor_id else None,
        "distributorName": _user_full_name(order.distributor),
        "parentOrderId": str(order.parent_order_id) if order.parent_order_id else None,
        "orderType": order.order_type,
        "status": order.status,
        "priceType": order.price_type,
        "discountPercent": float(order.discount_percent),
        "discountFlat": float(order.discount_flat),
        "subtotal": float(order.subtotal),
        "discountAmount": float(order.discount_amount),
        "totalAmount": float(order.total_amount),
        "notes": order.notes,
        "stockDeducted": order.stock_deducted,
        "itemCount": len(order.items),
        "placedAt": _ts(order.placed_at),
        "createdAt": order.created_at.isoformat(),
        "updatedAt": order.updated_at.isoformat(),
    }


def serialize_order(order: Order) -> dict:
    return {
        "id": str(order.id),
        "orderNumber": order.order_number,
        "tenantId": str(order.tenant_id),
        "tenantName": order.tenant.name if order.tenant else None,
        "shopId": str(order.shop_id),
        "shopName": order.shop.name if order.shop else None,
        "shopContactPerson": order.shop.contact_person if order.shop else None,
        "shopContactNumber": order.shop.contact_number if order.shop else None,
        "shopPhone": order.shop.phone if order.shop else None,
        "shopAddress": order.shop.address if order.shop else None,
        "createdBy": str(order.created_by),
        "createdByName": _user_full_name(order.creator),
        "assignedExecutive": str(order.assigned_executive) if order.assigned_executive else None,
        "assignedExecutiveName": _user_full_name(order.executive),
        "distributorId": str(order.distributor_id) if order.distributor_id else None,
        "distributorName": _user_full_name(order.distributor),
        "distributorPhone": order.distributor.phone if order.distributor else None,
        "parentOrderId": str(order.parent_order_id) if order.parent_order_id else None,
        "orderType": order.order_type,
        "status": order.status,
        "priceType": order.price_type,
        "discountPercent": float(order.discount_percent),
        "discountFlat": float(order.discount_flat),
        "subtotal": float(order.subtotal),
        "discountAmount": float(order.discount_amount),
        "totalAmount": float(order.total_amount),
        "notes": order.notes,
        "stockDeducted": order.stock_deducted,
        "deliveryPartner": order.delivery_partner,
        "trackingNumber": order.tracking_number,
        "trackingLink": order.tracking_link,
        "deliveryNotes": order.delivery_notes,
        "statusTimestamps": {
            "placedAt": _ts(order.placed_at),
            "verifiedAt": _ts(order.verified_at),
            "assignedAt": _ts(order.assigned_at),
            "approvedAt": _ts(order.approved_at),
            "estimatedAt": _ts(order.estimated_at),
            "billedAt": _ts(order.billed_at),
            "packingAt": _ts(order.packing_at),
            "dispatchedAt": _ts(order.dispatched_at),
            "deliveredAt": _ts(order.delivered_at),
            "cancelledAt": _ts(order.cancelled_at),
            "rejectedAt": _ts(order.rejected_at),
            "returnedAt": _ts(order.returned_at),
        },
        "items": [serialize_order_item(i) for i in order.items],
        "childOrders": [
            {
                "id": str(co.id),
                "orderNumber": co.order_number,
                "status": co.status,
                "orderType": co.order_type,
                "priceType": co.price_type,
                "subtotal": float(co.subtotal),
                "discountPercent": float(co.discount_percent),
                "discountFlat": float(co.discount_flat),
                "discountAmount": float(co.discount_amount),
                "totalAmount": float(co.total_amount),
                "notes": co.notes,
                "stockDeducted": co.stock_deducted,
                "isChild": co.parent_order_id is not None,
                "itemCount": len(co.items),
                "items": [serialize_order_item(i) for i in co.items],
                "placedAt": _ts(co.placed_at),
                "createdAt": co.created_at.isoformat(),
                "updatedAt": co.updated_at.isoformat(),
            }
            for co in order.child_orders
        ],
        "orderReturns": [serialize_order_return(r) for r in order.order_returns],
        "createdAt": order.created_at.isoformat(),
        "updatedAt": order.updated_at.isoformat(),
    }