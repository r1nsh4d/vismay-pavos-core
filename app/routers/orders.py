import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.common import CommonResponse, ResponseModel, ErrorResponseModel, PaginatedResponse
from app.schemas.order import (
    BundleOrderCreate, IndividualOrderCreate,
    OrderNoteUpdate, OrderDiscountUpdate,
    OrderAssignDistributorInput, OrderDispatchInput,
)
from app.services import orders as order_svc
from app.models.order import OrderStatus, OrderType
from app.models.user import User

router = APIRouter(prefix="/orders", tags=["Orders"])


# ── Search / Fetch ─────────────────────────────────────────────────────────────

@router.get("/search", response_model=CommonResponse)
async def search_orders(
    tenant_id: uuid.UUID | None = None,
    shop_id: uuid.UUID | None = None,
    distributor_id: uuid.UUID | None = None,
    assigned_executive: uuid.UUID | None = None,
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
        distributor_id=distributor_id,
        assigned_executive=assigned_executive,
        status=status, order_type=order_type,
        parent_only=parent_only, page=page, limit=limit,
    )
    return PaginatedResponse(
        data=[order_svc.serialize_order(o) for o in orders],
        message="Orders fetched", page=page, limit=limit, total=total,
    )


@router.get("/my", response_model=CommonResponse)
async def get_my_orders(
    status: OrderStatus | None = None,
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Executive sees only their own orders."""
    orders, total = await order_svc.search_orders(
        db, assigned_executive=current_user.id,
        status=status, page=page, limit=limit,
    )
    return PaginatedResponse(
        data=[order_svc.serialize_order(o) for o in orders],
        message="My orders fetched", page=page, limit=limit, total=total,
    )


@router.get("/distributor/my", response_model=CommonResponse)
async def get_my_distributor_orders(
    status: OrderStatus | None = None,
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Distributor sees only orders assigned to them."""
    orders, total = await order_svc.search_orders(
        db, distributor_id=current_user.id,
        status=status, page=page, limit=limit,
    )
    return PaginatedResponse(
        data=[order_svc.serialize_order(o) for o in orders],
        message="Distributor orders fetched", page=page, limit=limit, total=total,
    )


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


# ── Create ─────────────────────────────────────────────────────────────────────

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


# ── Admin / SCM transitions ────────────────────────────────────────────────────

@router.patch("/{order_id}/verify", response_model=CommonResponse)
async def verify_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status != OrderStatus.placed:
        return ErrorResponseModel(code=400, message="Only placed orders can be verified", error={})
    order = await order_svc.verify_order(db, order)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Order verified")


@router.patch("/{order_id}/assign-distributor", response_model=CommonResponse)
async def assign_distributor(
    order_id: uuid.UUID,
    assign_in: OrderAssignDistributorInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status != OrderStatus.verified:
        return ErrorResponseModel(code=400, message="Only verified orders can be assigned", error={})
    order = await order_svc.assign_distributor(db, order, assign_in.distributor_id)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Order assigned to distributor")


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


# ── Distributor transitions ────────────────────────────────────────────────────

@router.patch("/{order_id}/approve", response_model=CommonResponse)
async def approve_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status != OrderStatus.assigned:
        return ErrorResponseModel(code=400, message="Only assigned orders can be approved", error={})
    order = await order_svc.approve_order(db, order)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Order approved")


@router.patch("/{order_id}/hold", response_model=CommonResponse)
async def hold_order(
    order_id: uuid.UUID,
    body: OrderNoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status != OrderStatus.assigned:
        return ErrorResponseModel(code=400, message="Only assigned orders can be put on hold", error={})
    order = await order_svc.hold_order(db, order, notes=body.notes)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Order put on hold")


@router.patch("/{order_id}/reject", response_model=CommonResponse)
async def reject_order(
    order_id: uuid.UUID,
    body: OrderNoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status != OrderStatus.assigned:
        return ErrorResponseModel(code=400, message="Only assigned orders can be rejected", error={})
    order = await order_svc.reject_order(db, order, notes=body.notes)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Order rejected")


# ── Executive / SCM transitions ────────────────────────────────────────────────

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
        return ErrorResponseModel(code=400, message="Only approved orders can be estimated", error={})
    order = await order_svc.estimate_order(db, order)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Order estimated")


@router.patch("/{order_id}/bill", response_model=CommonResponse)
async def bill_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status != OrderStatus.estimated:
        return ErrorResponseModel(code=400, message="Only estimated orders can be billed", error={})
    order = await order_svc.bill_order(db, order)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Order billed")


@router.patch("/{order_id}/counting", response_model=CommonResponse)
async def move_to_counting(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status != OrderStatus.billed:
        return ErrorResponseModel(code=400, message="Only billed orders can move to counting", error={})
    order = await order_svc.move_to_counting(db, order)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Order moved to counting")


@router.patch("/{order_id}/packing", response_model=CommonResponse)
async def move_to_packing(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status != OrderStatus.counting:
        return ErrorResponseModel(code=400, message="Only counting orders can move to packing", error={})
    order = await order_svc.move_to_packing(db, order)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Order moved to packing")


@router.patch("/{order_id}/dispatch", response_model=CommonResponse)
async def dispatch_order(
    order_id: uuid.UUID,
    dispatch_in: OrderDispatchInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status != OrderStatus.packing:
        return ErrorResponseModel(code=400, message="Only packed orders can be dispatched", error={})
    order = await order_svc.dispatch_order(
        db, order,
        delivery_partner=dispatch_in.delivery_partner,
        tracking_number=dispatch_in.tracking_number,
        delivery_notes=dispatch_in.delivery_notes,
    )
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Order dispatched")


@router.patch("/{order_id}/deliver", response_model=CommonResponse)
async def deliver_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status != OrderStatus.dispatched:
        return ErrorResponseModel(code=400, message="Only dispatched orders can be delivered", error={})
    order = await order_svc.deliver_order(db, order)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Order delivered")


@router.patch("/{order_id}/return", response_model=CommonResponse)
async def return_order(
    order_id: uuid.UUID,
    body: OrderNoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status != OrderStatus.delivered:
        return ErrorResponseModel(code=400, message="Only delivered orders can be returned", error={})
    order = await order_svc.return_order(db, order, notes=body.notes)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Order returned")


# ── Delete ─────────────────────────────────────────────────────────────────────

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
