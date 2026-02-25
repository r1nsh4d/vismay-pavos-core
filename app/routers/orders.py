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
from app.schemas.common import ResponseModel
from app.schemas.order import OrderCreate, OrderResponse, OrderStatusUpdateRequest

router = APIRouter(prefix="/orders", tags=["Orders"])

now = lambda: datetime.now(timezone.utc)


async def _load_order(db, order_id: int) -> Order | None:
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.allocations))
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
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    offset = (page - 1) * page_size
    query = select(Order).options(selectinload(Order.items))
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
    result = await db.execute(query.order_by(Order.created_at.desc()).offset(offset).limit(page_size))
    orders = [OrderResponse.model_validate(o).model_dump() for o in result.scalars().all()]

    return ResponseModel(
        data={"total": total, "page": page, "page_size": page_size, "results": orders},
        message="Orders fetched successfully",
    )


@router.get("/{order_id}")
async def get_order(order_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    order = await _load_order(db, order_id)
    if not order:
        raise AppException(status_code=404, detail="Order not found", error_code="NOT_FOUND")
    return ResponseModel(data=OrderResponse.model_validate(order).model_dump(), message="Order fetched successfully")


# ─── Create (Executive places order) ─────────────────────────────────────────

@router.post("", status_code=201)
async def create_order(
    payload: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate all products belong to the selected category
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
    return ResponseModel(data=OrderResponse.model_validate(order).model_dump(), message="Order placed successfully")


# ─── PLACED → SUBMITTED (executive submits to admin) ─────────────────────────

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
    if payload.notes: order.notes = payload.notes
    await db.flush()

    return ResponseModel(data=OrderResponse.model_validate(order).model_dump(), message="Order submitted successfully")


# ─── SUBMITTED → FORWARDED (admin forwards to distributor) ───────────────────

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
    if payload.notes: order.notes = payload.notes
    await db.flush()

    return ResponseModel(data=OrderResponse.model_validate(order).model_dump(), message="Order forwarded to distributor")


# ─── FORWARDED → APPROVED / HOLD / CANCELLED (distributor) ───────────────────

@router.patch("/{order_id}/approve")
async def approve_order(order_id: int, payload: OrderStatusUpdateRequest, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    order = await _load_order(db, order_id)
    if not order:
        raise AppException(status_code=404, detail="Order not found", error_code="NOT_FOUND")
    if order.status != OrderStatus.FORWARDED:
        raise AppException(status_code=400, detail="Order must be in FORWARDED status", error_code="INVALID_STATUS")
    order.status = OrderStatus.APPROVED
    order.approved_at = now()
    if payload.notes: order.notes = payload.notes
    await db.flush()
    return ResponseModel(data=OrderResponse.model_validate(order).model_dump(), message="Order approved")


@router.patch("/{order_id}/hold")
async def hold_order(order_id: int, payload: OrderStatusUpdateRequest, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    order = await _load_order(db, order_id)
    if not order:
        raise AppException(status_code=404, detail="Order not found", error_code="NOT_FOUND")
    if order.status != OrderStatus.FORWARDED:
        raise AppException(status_code=400, detail="Order must be in FORWARDED status", error_code="INVALID_STATUS")
    order.status = OrderStatus.HOLD
    if payload.notes: order.notes = payload.notes
    await db.flush()
    return ResponseModel(data=OrderResponse.model_validate(order).model_dump(), message="Order placed on hold")


@router.patch("/{order_id}/cancel")
async def cancel_order(order_id: int, payload: OrderStatusUpdateRequest, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    order = await _load_order(db, order_id)
    if not order:
        raise AppException(status_code=404, detail="Order not found", error_code="NOT_FOUND")
    if order.status not in (OrderStatus.FORWARDED, OrderStatus.HOLD):
        raise AppException(status_code=400, detail="Order can only be cancelled from FORWARDED or HOLD", error_code="INVALID_STATUS")
    order.status = OrderStatus.CANCELLED
    if payload.notes: order.notes = payload.notes
    await db.flush()
    return ResponseModel(data=OrderResponse.model_validate(order).model_dump(), message="Order cancelled")


# ─── APPROVED → ESTIMATED (admin triggers stock check + auto-split) ───────────

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

    child_items = []  # items that need a child order

    for item in order.items:
        # Check total available stock for this product (FIFO order)
        result = await db.execute(
            select(Stock)
            .where(
                Stock.tenant_id == order.tenant_id,
                Stock.product_id == item.product_id,
                Stock.boxes_available > 0,
                Stock.is_active == True,
            )
            .order_by(Stock.created_at.asc())  # FIFO
        )
        batches = result.scalars().all()
        total_available = sum(b.boxes_available for b in batches)

        if total_available >= item.boxes_requested:
            # Full stock available
            item.boxes_fulfilled = item.boxes_requested
            item.boxes_pending = 0
        elif total_available > 0:
            # Partial stock
            item.boxes_fulfilled = total_available
            item.boxes_pending = item.boxes_requested - total_available
            child_items.append({"product_id": item.product_id, "boxes_requested": item.boxes_pending})
        else:
            # No stock at all
            item.boxes_fulfilled = 0
            item.boxes_pending = item.boxes_requested
            child_items.append({"product_id": item.product_id, "boxes_requested": item.boxes_pending})

    order.status = OrderStatus.ESTIMATED
    order.estimated_at = now()
    if payload.notes: order.notes = payload.notes
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
            status=OrderStatus.ESTIMATED,  # child skips directly to ESTIMATED
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
                boxes_fulfilled=ci["boxes_requested"],  # assume will be filled when stock arrives
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


# ─── ESTIMATED → BILLED (stock reserved — FIFO allocation) ───────────────────

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

        # FIFO — get oldest batches first
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
    if payload.notes: order.notes = payload.notes
    await db.flush()

    order = await _load_order(db, order.id)
    return ResponseModel(data=OrderResponse.model_validate(order).model_dump(), message="Order billed and stock reserved")


# ─── Simple status progression: BILLED → COUNTING → PACKING → DISPATCHED → DELIVERED

async def _advance_status(db, order_id, from_status, to_status, timestamp_field, message):
    order = await _load_order(db, order_id)
    if not order:
        raise AppException(status_code=404, detail="Order not found", error_code="NOT_FOUND")
    if order.status != from_status:
        raise AppException(status_code=400, detail=f"Order must be in {from_status} status", error_code="INVALID_STATUS")
    order.status = to_status
    if timestamp_field:
        setattr(order, timestamp_field, now())
    await db.flush()
    return order


@router.patch("/{order_id}/counting")
async def mark_counting(order_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    order = await _advance_status(db, order_id, OrderStatus.BILLED, OrderStatus.COUNTING, None, "Order moved to counting")
    return ResponseModel(data=OrderResponse.model_validate(order).model_dump(), message="Order moved to COUNTING")


@router.patch("/{order_id}/packing")
async def mark_packing(order_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    order = await _advance_status(db, order_id, OrderStatus.COUNTING, OrderStatus.PACKING, None, "Order moved to packing")
    return ResponseModel(data=OrderResponse.model_validate(order).model_dump(), message="Order moved to PACKING")


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

    # Move stock: reserved → dispatched
    for item in order.items:
        for allocation in item.allocations:
            stock = await db.scalar(select(Stock).where(Stock.id == allocation.stock_id))
            if stock:
                stock.boxes_reserved -= allocation.boxes_allocated
                stock.boxes_billed -= 0  # billed stage was reservation
                stock.boxes_dispatched += allocation.boxes_allocated

    order.status = OrderStatus.DISPATCHED
    order.dispatched_at = now()
    await db.flush()

    order = await _load_order(db, order.id)
    return ResponseModel(data=OrderResponse.model_validate(order).model_dump(), message="Order dispatched")


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

    # Finalize: deduct from total stock
    for item in order.items:
        for allocation in item.allocations:
            stock = await db.scalar(select(Stock).where(Stock.id == allocation.stock_id))
            if stock:
                stock.boxes_dispatched -= allocation.boxes_allocated
                stock.boxes_total -= allocation.boxes_allocated  # permanent deduction

    order.status = OrderStatus.DELIVERED
    order.delivered_at = now()
    await db.flush()

    order = await _load_order(db, order.id)
    return ResponseModel(data=OrderResponse.model_validate(order).model_dump(), message="Order delivered")