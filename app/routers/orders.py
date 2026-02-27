import uuid
from datetime import datetime, timezone
from typing import Optional, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.database import get_db
from app.dependencies import get_current_user
from app.models.order import Order, OrderItem, OrderItemAllocation, OrderStatus
from app.models.product import Product
from app.models.stock import Stock
from app.models.user import User
from app.schemas.common import ResponseModel, PaginatedResponse
from app.schemas.order import OrderCreate, OrderResponse, OrderStatusUpdateRequest

router = APIRouter(prefix="/orders", tags=["Orders"])


def now():
    return datetime.now(timezone.utc)


async def _load_order(db: AsyncSession, order_id: uuid.UUID) -> Optional[Order]:
    """Reload order with all nested relations using UUID."""
    result = await db.execute(
        select(Order)
        .options(
            selectinload(Order.items).selectinload(OrderItem.allocations)
        )
        .where(Order.id == order_id)
    )
    return result.scalar_one_or_none()


# ─── List ─────────────────────────────────────────────────────────────────────

@router.get("")
async def list_orders(
    tenant_id: uuid.UUID | None = Query(None),
    shop_id: uuid.UUID | None = Query(None),
    category_id: uuid.UUID | None = Query(None),
    status: OrderStatus | None = Query(None),
    placed_by: uuid.UUID | None = Query(None),
    parent_order_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    offset = (page - 1) * limit
    query = select(Order).options(
        selectinload(Order.items).selectinload(OrderItem.allocations)
    )
    count_query = select(func.count()).select_from(Order)

    if tenant_id:
        query = query.where(Order.tenant_id == tenant_id)
        count_query = count_query.where(Order.tenant_id == tenant_id)
    if shop_id:
        query = query.where(Order.shop_id == shop_id)
        count_query = count_query.where(Order.shop_id == shop_id)
    if category_id:
        query = query.where(Order.category_id == category_id)
        count_query = count_query.where(Order.category_id == category_id)
    if status:
        query = query.where(Order.status == status)
        count_query = count_query.where(Order.status == status)
    if placed_by:
        query = query.where(Order.placed_by == placed_by)
        count_query = count_query.where(Order.placed_by == placed_by)
    if parent_order_id is not None:
        query = query.where(Order.parent_order_id == parent_order_id)
        count_query = count_query.where(Order.parent_order_id == parent_order_id)

    total = await db.scalar(count_query) or 0
    result = await db.execute(
        query.order_by(Order.created_at.desc()).offset(offset).limit(limit)
    )
    orders = [OrderResponse.model_validate(o).model_dump() for o in result.scalars().all()]

    return PaginatedResponse(
        data=orders,
        message="Orders fetched successfully",
        page=page,
        limit=limit,
        total=total,
    )


# ─── Get by ID ────────────────────────────────────────────────────────────────

@router.get("/{order_id}")
async def get_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    order = await _load_order(db, order_id)
    if not order:
        raise AppException(status_code=404, detail="Order not found", error_code="NOT_FOUND")
    return ResponseModel(
        data=OrderResponse.model_validate(order).model_dump(),
        message="Order fetched successfully",
    )


# ─── Create ───────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_order(
    payload: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product_ids = [item.product_id for item in payload.items]
    result = await db.execute(
        select(Product.id).where(
            Product.id.in_(product_ids),
            Product.category_id == payload.category_id,
            Product.tenant_id == payload.tenant_id,
        )
    )
    valid_products = {p for p in result.scalars().all()}
    invalid = set(product_ids) - valid_products
    if invalid:
        raise AppException(
            status_code=400,
            detail=f"Products {invalid} do not belong to selected category/tenant",
            error_code="INVALID_PRODUCTS",
        )

    order_ref = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    order = Order(
        tenant_id=payload.tenant_id,
        shop_id=payload.shop_id,
        category_id=payload.category_id,
        placed_by=current_user.id,
        status=OrderStatus.PLACED,
        order_ref=order_ref,
        notes=payload.notes,
    )
    db.add(order)
    await db.flush()

    for item in payload.items:
        db.add(OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            boxes_requested=item.boxes_requested,
            boxes_fulfilled=0,
            boxes_pending=0,
        ))
    await db.flush()

    order = await _load_order(db, order.id)
    return ResponseModel(
        data=OrderResponse.model_validate(order).model_dump(),
        message="Order placed successfully",
    )


# ─── Status Transitions ───────────────────────────────────────────────────────

@router.patch("/{order_id}/submit")
async def submit_order(order_id: uuid.UUID, payload: OrderStatusUpdateRequest, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    order = await _load_order(db, order_id)
    if not order or order.status != OrderStatus.PLACED:
        raise AppException(status_code=400, detail="Invalid order or status", error_code="INVALID_STATUS")
    order.status = OrderStatus.SUBMITTED
    order.submitted_at = now()
    if payload.notes: order.notes = payload.notes
    await db.flush()
    return ResponseModel(data=OrderResponse.model_validate(order).model_dump(), message="Order submitted")


@router.patch("/{order_id}/forward")
async def forward_order(order_id: uuid.UUID, payload: OrderStatusUpdateRequest, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    order = await _load_order(db, order_id)
    if not order or order.status != OrderStatus.SUBMITTED:
        raise AppException(status_code=400, detail="Invalid status", error_code="INVALID_STATUS")
    order.status = OrderStatus.FORWARDED
    order.forwarded_at = now()
    if payload.notes: order.notes = payload.notes
    await db.flush()
    return ResponseModel(data=OrderResponse.model_validate(order).model_dump(), message="Order forwarded")


@router.patch("/{order_id}/approve")
async def approve_order(order_id: uuid.UUID, payload: OrderStatusUpdateRequest, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    order = await _load_order(db, order_id)
    if not order or order.status != OrderStatus.FORWARDED:
        raise AppException(status_code=400, detail="Invalid status", error_code="INVALID_STATUS")
    order.status = OrderStatus.APPROVED
    order.approved_at = now()
    if payload.notes: order.notes = payload.notes
    await db.flush()
    return ResponseModel(data=OrderResponse.model_validate(order).model_dump(), message="Order approved")


# ─── APPROVED → ESTIMATED (Stock Check & Split) ───────────────────────────────

@router.patch("/{order_id}/estimate")
async def estimate_order(
    order_id: uuid.UUID,
    payload: OrderStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    order = await _load_order(db, order_id)
    if not order or order.status != OrderStatus.APPROVED:
        raise AppException(status_code=400, detail="Invalid status", error_code="INVALID_STATUS")

    child_items = []

    for item in order.items:
        result = await db.execute(
            select(Stock)
            .where(
                Stock.tenant_id == order.tenant_id,
                Stock.product_id == item.product_id,
                Stock.boxes_available > 0,
                Stock.is_active == True,
            )
            .order_by(Stock.created_at.asc())
        )
        batches = result.scalars().all()
        total_available = sum(b.boxes_available for b in batches)

        if total_available >= item.boxes_requested:
            item.boxes_fulfilled = item.boxes_requested
            item.boxes_pending = 0
        else:
            item.boxes_fulfilled = total_available
            item.boxes_pending = item.boxes_requested - total_available
            child_items.append({"product_id": item.product_id, "boxes_requested": item.boxes_pending})

    order.status = OrderStatus.ESTIMATED
    order.estimated_at = now()
    if payload.notes: order.notes = payload.notes
    await db.flush()

    child_order_data = None
    if child_items:
        child_order = Order(
            tenant_id=order.tenant_id,
            shop_id=order.shop_id,
            category_id=order.category_id,
            placed_by=order.placed_by,
            parent_order_id=order.id,
            status=OrderStatus.PLACED,
            order_ref=f"ORD-{uuid.uuid4().hex[:8].upper()}",
            notes=f"Back-order for {order.order_ref}",
        )
        db.add(child_order)
        await db.flush()
        for ci in child_items:
            db.add(OrderItem(order_id=child_order.id, product_id=ci["product_id"], boxes_requested=ci["boxes_requested"], boxes_fulfilled=0, boxes_pending=0))
        await db.flush()
        child_order_data = OrderResponse.model_validate(await _load_order(db, child_order.id)).model_dump()

    return ResponseModel(
        data={"order": OrderResponse.model_validate(order).model_dump(), "child_order": child_order_data},
        message="Order estimated successfully"
    )


# ─── Fulfillment Steps (Billed, Packing, Dispatch, Deliver) ───────────────────

@router.patch("/{order_id}/bill")
async def bill_order(order_id: uuid.UUID, payload: OrderStatusUpdateRequest, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    order = await _load_order(db, order_id)
    if not order or order.status != OrderStatus.ESTIMATED:
        raise AppException(status_code=400, detail="Invalid status", error_code="INVALID_STATUS")

    for item in order.items:
        if item.boxes_fulfilled <= 0: continue
        boxes_needed = item.boxes_fulfilled
        result = await db.execute(
            select(Stock).where(Stock.tenant_id == order.tenant_id, Stock.product_id == item.product_id, Stock.boxes_available > 0).order_by(Stock.created_at.asc())
        )
        for batch in result.scalars().all():
            if boxes_needed <= 0: break
            allocate = min(batch.boxes_available, boxes_needed)
            batch.boxes_available -= allocate
            batch.boxes_reserved += allocate
            boxes_needed -= allocate
            db.add(OrderItemAllocation(order_item_id=item.id, stock_id=batch.id, boxes_allocated=allocate))

    order.status = OrderStatus.BILLED
    order.billed_at = now()
    await db.flush()
    return ResponseModel(data=OrderResponse.model_validate(order).model_dump(), message="Stock reserved and billed")


@router.patch("/{order_id}/dispatch")
async def dispatch_order(order_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    order = await _load_order(db, order_id)
    if not order or order.status != OrderStatus.BILLED: # simplified path for now
        raise AppException(status_code=400, detail="Invalid status", error_code="INVALID_STATUS")

    for item in order.items:
        for alloc in item.allocations:
            stock = await db.get(Stock, alloc.stock_id)
            stock.boxes_reserved -= alloc.boxes_allocated
            stock.boxes_dispatched += alloc.boxes_allocated

    order.status = OrderStatus.DISPATCHED
    order.dispatched_at = now()
    await db.flush()
    return ResponseModel(data=OrderResponse.model_validate(order).model_dump(), message="Order dispatched")


@router.patch("/{order_id}/deliver")
async def deliver_order(order_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    order = await _load_order(db, order_id)
    if not order or order.status != OrderStatus.DISPATCHED:
        raise AppException(status_code=400, detail="Invalid status", error_code="INVALID_STATUS")

    for item in order.items:
        for alloc in item.allocations:
            stock = await db.get(Stock, alloc.stock_id)
            stock.boxes_dispatched -= alloc.boxes_allocated
            stock.boxes_total -= alloc.boxes_allocated # Final deduction

    order.status = OrderStatus.DELIVERED
    order.delivered_at = now()
    await db.flush()
    return ResponseModel(data=OrderResponse.model_validate(order).model_dump(), message="Order delivered")