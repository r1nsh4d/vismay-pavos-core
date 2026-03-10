import uuid
from typing import List, Tuple, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import HTTPException

from app.models.order import Order, OrderItem, OrderStatus, OrderItemType
from app.schemas.order import OrderCreate, OrderUpdate
from app.services.stocks import adjust_stock


def _order_query():
    return select(Order).options(selectinload(Order.items))


async def get_order_by_id(db: AsyncSession, order_id: uuid.UUID) -> Order | None:
    result = await db.execute(_order_query().where(Order.id == order_id))
    return result.scalar_one_or_none()


async def get_orders(
    db: AsyncSession,
    tenant_id: Optional[uuid.UUID] = None,
    shop_id: Optional[uuid.UUID] = None,
    status: Optional[OrderStatus] = None,
    page: int = 1,
    limit: int = 20,
) -> Tuple[List[Order], int]:
    query = _order_query()
    if tenant_id:
        query = query.where(Order.tenant_id == tenant_id)
    if shop_id:
        query = query.where(Order.shop_id == shop_id)
    if status:
        query = query.where(Order.status == status)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    result = await db.execute(query.offset((page - 1) * limit).limit(limit))
    return result.scalars().all(), total


async def create_order(db: AsyncSession, order_in: OrderCreate, created_by: uuid.UUID) -> Order:
    order = Order(
        tenant_id=order_in.tenant_id,
        shop_id=order_in.shop_id,
        created_by=created_by,
        notes=order_in.notes,
        status=OrderStatus.estimated,
        total_amount=0,
    )
    db.add(order)
    await db.flush()

    total = 0.0
    for item_in in order_in.items:
        total_price = item_in.unit_price * item_in.quantity
        db.add(OrderItem(
            order_id=order.id,
            variant_id=item_in.variant_id,
            item_type=item_in.item_type,
            quantity=item_in.quantity,
            unit_price=item_in.unit_price,
            total_price=total_price,
        ))
        total += total_price

    order.total_amount = total
    await db.flush()

    result = await db.execute(_order_query().where(Order.id == order.id))
    return result.scalar_one()


async def update_order_status(
    db: AsyncSession, order: Order, new_status: OrderStatus
) -> Order:
    old_status = order.status

    # Deduct stock when confirmed
    if new_status == OrderStatus.confirmed and old_status != OrderStatus.confirmed:
        for item in order.items:
            if item.item_type == OrderItemType.individual:
                await adjust_stock(db, item.variant_id, individual_delta=-item.quantity)
            else:
                await adjust_stock(db, item.variant_id, bundle_delta=-item.quantity)

    # Restore stock if cancelled after confirmation
    if new_status == OrderStatus.cancelled and old_status == OrderStatus.confirmed:
        for item in order.items:
            if item.item_type == OrderItemType.individual:
                await adjust_stock(db, item.variant_id, individual_delta=item.quantity)
            else:
                await adjust_stock(db, item.variant_id, bundle_delta=item.quantity)

    order.status = new_status
    await db.flush()
    result = await db.execute(_order_query().where(Order.id == order.id))
    return result.scalar_one()


async def update_order(db: AsyncSession, order: Order, order_in: OrderUpdate) -> Order:
    if order_in.notes is not None:
        order.notes = order_in.notes
    if order_in.status is not None:
        return await update_order_status(db, order, order_in.status)
    await db.flush()
    result = await db.execute(_order_query().where(Order.id == order.id))
    return result.scalar_one()


async def delete_order(db: AsyncSession, order: Order) -> None:
    if order.status not in (OrderStatus.estimated, OrderStatus.cancelled):
        raise HTTPException(status_code=400, detail="Only estimated or cancelled orders can be deleted")
    await db.delete(order)
    await db.flush()