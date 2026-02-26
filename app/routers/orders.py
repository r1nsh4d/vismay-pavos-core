import uuid
from datetime import datetime, timezone
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


async def _load_order(db: AsyncSession, order_id: int) -> Order | None:
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
    tenant_id: int | None = Query(None),
    shop_id: int | None = Query(None),
    category_id: int | None = Query(None),
    status: OrderStatus | None = Query(None),
    placed_by: int | None = Query(None),
    parent_order_id: int | None = Query(None),
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

    filters = []
    if tenant_id: filters.append(Order.tenant_id == tenant_id)
    if shop_id: filters.append(Order.shop_id == shop_id)
    if category_id: filters.append(Order.category_id == category_id)
    if status: filters.append(Order.status == status)
    if placed_by: filters.append(Order.placed_by == placed_by)
    if parent_order_id is not None:
        filters.append(Order.parent_order_id == parent_order_id)

    for f in filters:
        query = query.where(f)
        count_query = count_query.where(f)

    total = await db.scalar(count_query)
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
    order_id: int,
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
        select(Product).where(
            Product.id.in_(product_ids),
            Product.category_id == payload.category_id,
            Product.tenant_id == payload.tenant_id,
        )
    )
    valid_products = {p.id for p in result.scalars().all()}
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


# ─── PLACED → SUBMITTED ───────────────────────────────────────────────────────

@router.patch("/{order_id}/submit")
async def submit_order(
    order_id: int,
    payload: OrderStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    order = await _load_order(db, order_id)
    if not order:
        raise AppException(status_code=404, detail="Order not found", error_code="NOT_FOUND")
    if order.status != OrderStatus.PLACED:
        raise AppException(status_code=400, detail="Order must be in PLACED status", error_code="INVALID_STATUS")

    order.status = OrderStatus.SUBMITTED
    order.submitted_at = now()
    if payload.notes:
        order.notes = payload.notes
    await db.flush()

    order = await _load_order(db, order.id)
    return ResponseModel(
        data=OrderResponse.model_validate(order).model_dump(),
        message="Order submitted successfully",
    )


# ─── SUBMITTED → FORWARDED ────────────────────────────────────────────────────

@router.patch("/{order_id}/forward")
async def forward_order(
    order_id: int,
    payload: OrderStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    order = await _load_order(db, order_id)
    if not order:
        raise AppException(status_code=404, detail="Order not found", error_code="NOT_FOUND")
    if order.status != OrderStatus.SUBMITTED:
        raise AppException(status_code=400, detail="Order must be in SUBMITTED status", error_code="INVALID_STATUS")

    order.status = OrderStatus.FORWARDED
    order.forwarded_at = now()
    if payload.notes:
        order.notes = payload.notes
    await db.flush()

    order = await _load_order(db, order.id)
    return ResponseModel(
        data=OrderResponse.model_validate(order).model_dump(),
        message="Order forwarded to distributor",
    )


# ─── FORWARDED → APPROVED ─────────────────────────────────────────────────────

@router.patch("/{order_id}/approve")
async def approve_order(
    order_id: int,
    payload: OrderStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    order = await _load_order(db, order_id)
    if not order:
        raise AppException(status_code=404, detail="Order not found", error_code="NOT_FOUND")
    if order.status != OrderStatus.FORWARDED:
        raise AppException(status_code=400, detail="Order must be in FORWARDED status", error_code="INVALID_STATUS")

    order.status = OrderStatus.APPROVED
    order.approved_at = now()
    if payload.notes:
        order.notes = payload.notes
    await db.flush()

    order = await _load_order(db, order.id)
    return ResponseModel(
        data=OrderResponse.model_validate(order).model_dump(),
        message="Order approved",
    )


# ─── FORWARDED → HOLD ─────────────────────────────────────────────────────────

@router.patch("/{order_id}/hold")
async def hold_order(
    order_id: int,
    payload: OrderStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    order = await _load_order(db, order_id)
    if not order:
        raise AppException(status_code=404, detail="Order not found", error_code="NOT_FOUND")
    if order.status != OrderStatus.FORWARDED:
        raise AppException(status_code=400, detail="Order must be in FORWARDED status", error_code="INVALID_STATUS")

    order.status = OrderStatus.HOLD
    if payload.notes:
        order.notes = payload.notes
    await db.flush()

    order = await _load_order(db, order.id)
    return ResponseModel(
        data=OrderResponse.model_validate(order).model_dump(),
        message="Order placed on hold",
    )


# ─── FORWARDED/HOLD → CANCELLED ───────────────────────────────────────────────

@router.patch("/{order_id}/cancel")
async def cancel_order(
    order_id: int,
    payload: OrderStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    order = await _load_order(db, order_id)
    if not order:
        raise AppException(status_code=404, detail="Order not found", error_code="NOT_FOUND")
    if order.status not in (OrderStatus.FORWARDED, OrderStatus.HOLD):
        raise AppException(
            status_code=400,
            detail="Order can only be cancelled from FORWARDED or HOLD",
            error_code="INVALID_STATUS",
        )

    order.status = OrderStatus.CANCELLED
    if payload.notes:
        order.notes = payload.notes
    await db.flush()

    order = await _load_order(db, order.id)
    return ResponseModel(
        data=OrderResponse.model_validate(order).model_dump(),
        message="Order cancelled",
    )


# ─── APPROVED → ESTIMATED (stock check + auto-split) ─────────────────────────

@router.patch("/{order_id}/estimate")
async def estimate_order(
    order_id: int,
    payload: OrderStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    order = await _load_order(db, order_id)
    if not order:
        raise AppException(status_code=404, detail="Order not found", error_code="NOT_FOUND")
    if order.status != OrderStatus.APPROVED:
        raise AppException(status_code=400, detail="Order must be in APPROVED status", error_code="INVALID_STATUS")

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
        elif total_available > 0:
            item.boxes_fulfilled = total_available
            item.boxes_pending = item.boxes_requested - total_available
            child_items.append({
                "product_id": item.product_id,
                "boxes_requested": item.boxes_pending,
            })
        else:
            item.boxes_fulfilled = 0
            item.boxes_pending = item.boxes_requested
            child_items.append({
                "product_id": item.product_id,
                "boxes_requested": item.boxes_pending,
            })

    order.status = OrderStatus.ESTIMATED
    order.estimated_at = now()
    if payload.notes:
        order.notes = payload.notes
    await db.flush()

    # Create child order for pending items
    child_order = None
    if child_items:
        child_ref = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        child_order = Order(
            tenant_id=order.tenant_id,
            shop_id=order.shop_id,
            category_id=order.category_id,
            placed_by=order.placed_by,
            parent_order_id=order.id,
            status=OrderStatus.ESTIMATED,
            order_ref=child_ref,
            notes=f"Child order of {order.order_ref}",
            estimated_at=now(),
        )
        db.add(child_order)
        await db.flush()

        for ci in child_items:
            db.add(OrderItem(
                order_id=child_order.id,
                product_id=ci["product_id"],
                boxes_requested=ci["boxes_requested"],
                boxes_fulfilled=ci["boxes_requested"],
                boxes_pending=0,
            ))
        await db.flush()
        child_order = await _load_order(db, child_order.id)

    order = await _load_order(db, order.id)
    return ResponseModel(
        data={
            "order": OrderResponse.model_validate(order).model_dump(),
            "child_order": OrderResponse.model_validate(child_order).model_dump() if child_order else None,
        },
        message="Order estimated successfully",
    )


# ─── ESTIMATED → BILLED (FIFO stock reservation) ─────────────────────────────

@router.patch("/{order_id}/bill")
async def bill_order(
    order_id: int,
    payload: OrderStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    order = await _load_order(db, order_id)
    if not order:
        raise AppException(status_code=404, detail="Order not found", error_code="NOT_FOUND")
    if order.status != OrderStatus.ESTIMATED:
        raise AppException(status_code=400, detail="Order must be in ESTIMATED status", error_code="INVALID_STATUS")

    for item in order.items:
        if item.boxes_fulfilled == 0:
            continue

        boxes_needed = item.boxes_fulfilled

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

        for batch in batches:
            if boxes_needed <= 0:
                break
            allocate = min(batch.boxes_available, boxes_needed)
            batch.boxes_available -= allocate
            batch.boxes_reserved += allocate
            boxes_needed -= allocate
            db.add(OrderItemAllocation(
                order_item_id=item.id,
                stock_id=batch.id,
                boxes_allocated=allocate,
            ))

        if boxes_needed > 0:
            raise AppException(
                status_code=400,
                detail=f"Insufficient stock for product {item.product_id} during billing",
                error_code="INSUFFICIENT_STOCK",
            )

    order.status = OrderStatus.BILLED
    order.billed_at = now()
    if payload.notes:
        order.notes = payload.notes
    await db.flush()

    order = await _load_order(db, order.id)
    return ResponseModel(
        data=OrderResponse.model_validate(order).model_dump(),
        message="Order billed and stock reserved",
    )


# ─── BILLED → COUNTING ────────────────────────────────────────────────────────

@router.patch("/{order_id}/counting")
async def mark_counting(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    order = await _load_order(db, order_id)
    if not order:
        raise AppException(status_code=404, detail="Order not found", error_code="NOT_FOUND")
    if order.status != OrderStatus.BILLED:
        raise AppException(status_code=400, detail="Order must be in BILLED status", error_code="INVALID_STATUS")

    order.status = OrderStatus.COUNTING
    await db.flush()

    order = await _load_order(db, order.id)
    return ResponseModel(
        data=OrderResponse.model_validate(order).model_dump(),
        message="Order moved to COUNTING",
    )


# ─── COUNTING → PACKING ───────────────────────────────────────────────────────

@router.patch("/{order_id}/packing")
async def mark_packing(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    order = await _load_order(db, order_id)
    if not order:
        raise AppException(status_code=404, detail="Order not found", error_code="NOT_FOUND")
    if order.status != OrderStatus.COUNTING:
        raise AppException(status_code=400, detail="Order must be in COUNTING status", error_code="INVALID_STATUS")

    order.status = OrderStatus.PACKING
    await db.flush()

    order = await _load_order(db, order.id)
    return ResponseModel(
        data=OrderResponse.model_validate(order).model_dump(),
        message="Order moved to PACKING",
    )


# ─── PACKING → DISPATCHED ─────────────────────────────────────────────────────

@router.patch("/{order_id}/dispatch")
async def dispatch_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    order = await _load_order(db, order_id)
    if not order:
        raise AppException(status_code=404, detail="Order not found", error_code="NOT_FOUND")
    if order.status != OrderStatus.PACKING:
        raise AppException(status_code=400, detail="Order must be in PACKING status", error_code="INVALID_STATUS")

    for item in order.items:
        for allocation in item.allocations:
            stock = await db.scalar(select(Stock).where(Stock.id == allocation.stock_id))
            if stock:
                stock.boxes_reserved -= allocation.boxes_allocated
                stock.boxes_dispatched += allocation.boxes_allocated
    await db.flush()

    order.status = OrderStatus.DISPATCHED
    order.dispatched_at = now()
    await db.flush()

    order = await _load_order(db, order.id)
    return ResponseModel(
        data=OrderResponse.model_validate(order).model_dump(),
        message="Order dispatched",
    )


# ─── DISPATCHED → DELIVERED ───────────────────────────────────────────────────

@router.patch("/{order_id}/deliver")
async def deliver_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    order = await _load_order(db, order_id)
    if not order:
        raise AppException(status_code=404, detail="Order not found", error_code="NOT_FOUND")
    if order.status != OrderStatus.DISPATCHED:
        raise AppException(status_code=400, detail="Order must be in DISPATCHED status", error_code="INVALID_STATUS")

    for item in order.items:
        for allocation in item.allocations:
            stock = await db.scalar(select(Stock).where(Stock.id == allocation.stock_id))
            if stock:
                stock.boxes_dispatched -= allocation.boxes_allocated
                stock.boxes_total -= allocation.boxes_allocated
    await db.flush()

    order.status = OrderStatus.DELIVERED
    order.delivered_at = now()
    await db.flush()

    order = await _load_order(db, order.id)
    return ResponseModel(
        data=OrderResponse.model_validate(order).model_dump(),
        message="Order delivered",
    )