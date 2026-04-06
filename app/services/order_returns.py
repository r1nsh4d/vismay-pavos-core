import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order, OrderItem, OrderStatus, OrderType
from app.models.order_return import OrderReturn, ReturnType
from app.models.product import ProductVariant
from app.models.set_type import SetTypeItem
from app.models.stock import Stock
from app.core.exceptions import AppException


# ── Fetch ──────────────────────────────────────────────────────────────────────

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


# ── Core return logic ──────────────────────────────────────────────────────────

async def process_return(
    db: AsyncSession,
    order: Order,
    return_input,
    processed_by: uuid.UUID,
) -> List[OrderReturn]:
    """
    Processes a return event for one or more items in an order.
    Each item specifies return_type (bundle/individual) and count.
    Stock is restored based on return_type regardless of original order_type.
    """
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
            raise AppException(
                status_code=400,
                detail=f"Return count must be greater than 0"
            )

        # check how much has already been returned for this item
        already_returned = (await db.execute(
            select(OrderReturn)
            .where(
                OrderReturn.order_item_id == ri.order_item_id,
                OrderReturn.order_id == order.id,
            )
        )).scalars().all()
        total_already_returned = sum(r.count for r in already_returned)

        if total_already_returned + ri.count > order_item.count:
            raise AppException(
                status_code=400,
                detail=f"Total returned count ({total_already_returned + ri.count}) "
                       f"exceeds original item count ({order_item.count}) "
                       f"for item {ri.order_item_id}"
            )

        # restore stock based on return_type
        await _restore_stock(
            db=db,
            order_item=order_item,
            return_type=ri.return_type,
            count=ri.count,
        )

        # create return record
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

    # update order status based on total return coverage
    await _update_order_return_status(db, order)

    await db.flush()
    return created_returns


async def _restore_stock(
    db: AsyncSession,
    order_item: OrderItem,
    return_type: ReturnType,
    count: int,
) -> None:
    """
    return_type=individual → adds to individual_count on Stock
    return_type=bundle     → adds to bundle_count on BundleStock
    This is independent of the original order_type —
    a bundle order item can be returned piece by piece as individual.
    """
    if return_type == ReturnType.individual:
        # restore as loose individual pieces
        # variant_id is set for individual orders
        # for bundle orders, we need to find the variant by size from set_type
        if order_item.variant_id:
            stock = await db.scalar(
                select(Stock).where(Stock.variant_id == order_item.variant_id)
            )
            if stock:
                stock.individual_count += count
        else:
            # bundle order item returned as individual pieces —
            # distribute across all variants in the set_type
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
                    # each bundle had si.quantity pieces of this size
                    stock.individual_count += count * si.quantity

    elif return_type == ReturnType.bundle:
        # restore as full bundles back to bundle stock
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
    """
    Checks total returned quantities across all return records for this order.
    fully returned  → OrderStatus. Returned
    partially       → OrderStatus.partially_returned
    """
    # sum all returns per order_item
    all_returns = (await db.execute(
        select(OrderReturn).where(OrderReturn.order_id == order.id)
    )).scalars().all()

    returned_by_item: dict[uuid.UUID, int] = {}
    for r in all_returns:
        returned_by_item[r.order_item_id] = (
            returned_by_item.get(r.order_item_id, 0) + r.count
        )

    total_ordered = sum(item.count for item in order.items)
    total_returned = sum(returned_by_item.get(item.id, 0) for item in order.items)

    if total_returned <= 0:
        pass  # no status change if nothing was returned yet
    elif total_returned >= total_ordered:
        order.status = OrderStatus.returned
    else:
        order.status = OrderStatus.partially_returned


# ── Serialization ──────────────────────────────────────────────────────────────

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
        "setTypeId": str(r.set_type_id) if r.set_type_id else None,
        "setTypeName": r.set_type.name if r.set_type else None,
        "returnType": r.return_type,
        "count": r.count,
        "processedBy": str(r.processed_by),
        "processedByName": processor_name,
        "notes": r.notes,
        "createdAt": r.created_at.isoformat(),
    }