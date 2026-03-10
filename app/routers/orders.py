import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.common import CommonResponse, ResponseModel, ErrorResponseModel, PaginatedResponse
from app.schemas.order import OrderCreate, OrderUpdate, OrderResponse
from app.models.order import OrderStatus
from app.services import orders as order_svc
from app.dependencies import get_current_user
from app.models import User

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("", response_model=CommonResponse)
async def create_order(
    order_in: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.create_order(db, order_in, created_by=current_user.id)
    return ResponseModel(data=OrderResponse.model_validate(order), message="Order created")


@router.get("", response_model=CommonResponse)
async def list_orders(
    tenant_id: uuid.UUID | None = None,
    shop_id: uuid.UUID | None = None,
    status: OrderStatus | None = None,
    page: int = 1, limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    orders, total = await order_svc.get_orders(db, tenant_id=tenant_id, shop_id=shop_id, status=status, page=page, limit=limit)
    return PaginatedResponse(data=[OrderResponse.model_validate(o) for o in orders], message="Orders fetched", page=page, limit=limit, total=total)


@router.get("/{order_id}", response_model=CommonResponse)
async def get_order(order_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    return ResponseModel(data=OrderResponse.model_validate(order), message="Order fetched")


@router.patch("/{order_id}/status", response_model=CommonResponse)
async def update_status(order_id: uuid.UUID, status: OrderStatus, db: AsyncSession = Depends(get_db)):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    order = await order_svc.update_order_status(db, order, status)
    return ResponseModel(data=OrderResponse.model_validate(order), message=f"Order status updated to {status}")


@router.put("/{order_id}", response_model=CommonResponse)
async def update_order(order_id: uuid.UUID, order_in: OrderUpdate, db: AsyncSession = Depends(get_db)):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    order = await order_svc.update_order(db, order, order_in)
    return ResponseModel(data=OrderResponse.model_validate(order), message="Order updated")


@router.delete("/{order_id}", response_model=CommonResponse)
async def delete_order(order_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    await order_svc.delete_order(db, order)
    return ResponseModel(data=None, message="Order deleted")