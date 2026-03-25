import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.common import CommonResponse, ResponseModel, ErrorResponseModel, PaginatedResponse
from app.schemas.order import (
    BundleOrderCreate, IndividualOrderCreate,
    OrderStatusNoteUpdate, OrderDiscountUpdate,
)
from app.services import orders as order_svc
from app.models.order import OrderStatus, OrderType
from app.models.user import User

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.get("/search", response_model=CommonResponse)
async def search_orders(
    tenant_id: uuid.UUID | None = None,
    shop_id: uuid.UUID | None = None,
    distributor_id: uuid.UUID | None = None,
    status: OrderStatus | None = None,
    order_type: OrderType | None = None,
    parent_only: bool = True,
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    orders, total = await order_svc.search_orders(
        db, tenant_id=tenant_id, shop_id=shop_id,
        distributor_id=distributor_id, status=status,
        order_type=order_type, parent_only=parent_only,
        page=page, limit=limit,
    )
    return PaginatedResponse(
        data=[order_svc.serialize_order(o) for o in orders],
        message="Orders fetched", page=page, limit=limit, total=total,
    )


@router.post("/bundle", response_model=CommonResponse)
async def create_bundle_order(
    order_in: BundleOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.create_bundle_order(db, order_in, created_by=current_user.id)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Bundle order created")


@router.post("/individual", response_model=CommonResponse)
async def create_individual_order(
    order_in: IndividualOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.create_individual_order(db, order_in, created_by=current_user.id)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Individual order created")


@router.get("/{order_id}", response_model=CommonResponse)
async def get_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    return ResponseModel(data=order_svc.serialize_order(order), message="Order fetched")


@router.patch("/{order_id}/status", response_model=CommonResponse)
async def update_order_status(
    order_id: uuid.UUID,
    status_in: OrderStatusNoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    order = await order_svc.update_status(db, order, status_in.status, notes=status_in.notes)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Order status updated")


@router.patch("/{order_id}/estimate", response_model=CommonResponse)
async def estimate_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status != OrderStatus.approved:
        return ErrorResponseModel(
            code=400, message="Only approved orders can be estimated", error={}
        )
    order = await order_svc.estimate_order(db, order)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Order estimated")


@router.patch("/{order_id}/discount", response_model=CommonResponse)
async def apply_discount(
    order_id: uuid.UUID,
    discount_in: OrderDiscountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    order = await order_svc.apply_discount(db, order, discount_in.discount_percent)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Discount applied")


@router.delete("/{order_id}", response_model=CommonResponse)
async def delete_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status not in (OrderStatus.placed, OrderStatus.rejected):
        return ErrorResponseModel(
            code=400, message="Only placed or rejected orders can be deleted", error={}
        )
    await order_svc.soft_delete_order(db, order)
    await db.commit()
    return ResponseModel(data=None, message="Order deleted")


# 1. Approve order (placed → approved)
@router.patch("/{order_id}/approve", response_model=CommonResponse)
async def approve_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status != OrderStatus.placed:
        return ErrorResponseModel(code=400, message="Only placed orders can be approved", error={})
    order = await order_svc.update_status(db, order, OrderStatus.approved)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Order approved")


# 2. Reject order (placed → rejected)
@router.patch("/{order_id}/reject", response_model=CommonResponse)
async def reject_order(
    order_id: uuid.UUID,
    status_in: OrderStatusNoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status != OrderStatus.placed:
        return ErrorResponseModel(code=400, message="Only placed orders can be rejected", error={})
    order = await order_svc.update_status(db, order, OrderStatus.rejected, notes=status_in.notes)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Order rejected")


# 3. Mark order as delivered (estimated → delivered)
@router.patch("/{order_id}/deliver", response_model=CommonResponse)
async def deliver_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status != OrderStatus.estimated:
        return ErrorResponseModel(code=400, message="Only estimated orders can be delivered", error={})
    order = await order_svc.update_status(db, order, OrderStatus.delivered)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Order marked as delivered")


# 4. Get orders by shop
@router.get("/shop/{shop_id}", response_model=CommonResponse)
async def get_orders_by_shop(
    shop_id: uuid.UUID,
    status: OrderStatus | None = None,
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    orders, total = await order_svc.search_orders(
        db, shop_id=shop_id, status=status, page=page, limit=limit
    )
    return PaginatedResponse(
        data=[order_svc.serialize_order(o) for o in orders],
        message="Shop orders fetched", page=page, limit=limit, total=total,
    )


# 5. Get orders by distributor
@router.get("/distributor/{distributor_id}", response_model=CommonResponse)
async def get_orders_by_distributor(
    distributor_id: uuid.UUID,
    status: OrderStatus | None = None,
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    orders, total = await order_svc.search_orders(
        db, distributor_id=distributor_id, status=status, page=page, limit=limit
    )
    return PaginatedResponse(
        data=[order_svc.serialize_order(o) for o in orders],
        message="Distributor orders fetched", page=page, limit=limit, total=total,
    )