import uuid
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.routers.reports import pdf_response
from app.schemas.common import CommonResponse, ResponseModel, ErrorResponseModel, PaginatedResponse
from app.schemas.order import (
    BundleOrderCreate, IndividualOrderCreate,
    OrderNoteUpdate, OrderDiscountUpdate,
    OrderAssignDistributorInput, OrderDispatchInput,
    SplitOrderInput, CreateOrderReturnInput,
    UpdateDeliveredAtInput, UpdateOrderItemInput, OrderBillUpdate,
)
from app.services import orders as order_svc
from app.models.order import OrderStatus, OrderType, CANCELLABLE_STATUSES
from app.models.user import User
from app.services.report_export import build_invoice_pdf

router = APIRouter(prefix="/orders", tags=["Orders"])


# ── Search / Fetch ─────────────────────────────────────────────────────────────

@router.get("/search", response_model=CommonResponse)
async def search_orders(
    q: str| None = None,
    tenant_id: uuid.UUID | None = None,
    shop_id: uuid.UUID | None = None,
    distributor_id: uuid.UUID | None = None,
    assigned_executive: uuid.UUID | None = None,
    status: OrderStatus | None = None,
    order_type: OrderType | None = None,
    parent_only: bool = True,
    date_from: date | None = None,
    date_to: date | None = None,
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
        parent_only=parent_only,
        date_from=date_from, date_to=date_to,
        search=q, page=page, limit=limit,
    )
    return PaginatedResponse(
        data=[order_svc.serialize_order_list(o) for o in orders],
        message="Orders fetched", page=page, limit=limit, total=total,
    )


@router.get("/my", response_model=CommonResponse)
async def get_my_orders(
    status: OrderStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    orders, total = await order_svc.search_orders(
        db, assigned_executive=current_user.id,
        status=status, date_from=date_from, date_to=date_to,
        page=page, limit=limit,
    )
    return PaginatedResponse(
        data=[order_svc.serialize_order_list(o) for o in orders],
        message="My orders fetched", page=page, limit=limit, total=total,
    )


@router.get("/distributor/my", response_model=CommonResponse)
async def get_my_distributor_orders(
    status: OrderStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    orders, total = await order_svc.search_orders(
        db, distributor_id=current_user.id,
        status=status, date_from=date_from, date_to=date_to,
        page=page, limit=limit,
    )
    return PaginatedResponse(
        data=[order_svc.serialize_order_list(o) for o in orders],
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


# ── Item edit (pre-bill) ───────────────────────────────────────────────────────

@router.patch("/{order_id}/items/{order_item_id}", response_model=CommonResponse)
async def update_order_item(
    order_id: uuid.UUID,
    order_item_id: uuid.UUID,
    item_in: UpdateOrderItemInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status not in (
        OrderStatus.placed, OrderStatus.verified,
        OrderStatus.assigned, OrderStatus.approved, OrderStatus.estimated,
    ):
        return ErrorResponseModel(
            code=400, message="Items can only be edited before billing", error={}
        )
    order = await order_svc.update_order_item(db, order, order_item_id, item_in.count)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Order item updated")


# ── Estimate & Split ───────────────────────────────────────────────────────────

@router.get("/{order_id}/estimate-split", response_model=CommonResponse)
async def get_estimate_split_preview(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    preview = await order_svc.get_estimate_split_preview(db, order)
    return ResponseModel(data=preview, message="Estimate split preview fetched")


@router.post("/{order_id}/split", response_model=CommonResponse)
async def split_order(
    order_id: uuid.UUID,
    split_in: SplitOrderInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status not in (
        OrderStatus.placed, OrderStatus.verified,
        OrderStatus.assigned, OrderStatus.approved, OrderStatus.estimated,
    ):
        return ErrorResponseModel(
            code=400, message="Orders can only be split before billing", error={}
        )
    new_order = await order_svc.split_order(db, order, split_in, created_by=current_user.id)
    await db.commit()
    return ResponseModel(
        data={
            "newOrder": order_svc.serialize_order(await order_svc.get_order_by_id(db, new_order.id)),
            "parentOrder": order_svc.serialize_order(await order_svc.get_order_by_id(db, order_id)),
        },
        message=f"Order split as {'child' if split_in.create_as == 'child' else 'new'} order"
    )


# ── Admin / SCM transitions ────────────────────────────────────────────────────

@router.patch("/{order_id}/verify", response_model=CommonResponse)
async def verify_order(
    order_id: uuid.UUID,
    body: OrderNoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status != OrderStatus.placed:
        return ErrorResponseModel(code=400, message="Only placed orders can be verified", error={})
    order = await order_svc.verify_order(db, order, notes=body.notes)
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
    order = await order_svc.assign_distributor(db, order, assign_in.distributor_id, notes=assign_in.notes)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Order assigned to distributor")


@router.patch("/{order_id}/cancel", response_model=CommonResponse)
async def cancel_order(
    order_id: uuid.UUID,
    body: OrderNoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    order = await order_svc.cancel_order(db, order, notes=body.notes)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Order cancelled")


@router.patch("/{order_id}/estimate", response_model=CommonResponse)
async def estimate_order(
    order_id: uuid.UUID,
    body: OrderNoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status != OrderStatus.approved:
        return ErrorResponseModel(code=400, message="Only approved orders can be estimated", error={})
    order = await order_svc.estimate_order(db, order, notes=body.notes)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Order estimated")


# ── Distributor transitions ────────────────────────────────────────────────────

@router.patch("/{order_id}/approve", response_model=CommonResponse)
async def approve_order(
    order_id: uuid.UUID,
    body: OrderNoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status not in (OrderStatus.assigned, OrderStatus.on_hold):
        return ErrorResponseModel(code=400, message="Only assigned orders can be approved", error={})
    order = await order_svc.approve_order(db, order, notes=body.notes)
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


@router.patch("/{order_id}/unhold", response_model=CommonResponse)
async def unhold_order(
    order_id: uuid.UUID,
    body: OrderNoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status != OrderStatus.on_hold:
        return ErrorResponseModel(code=400, message="Only on-hold orders can be unholded", error={})
    order = await order_svc.unhold_order(db, order, notes=body.notes)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Order unholded")


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


# ── Billing & discount ─────────────────────────────────────────────────────────

@router.patch("/{order_id}/bill", response_model=CommonResponse)
async def bill_order(
    order_id: uuid.UUID,
    body: OrderBillUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status != OrderStatus.estimated:
        return ErrorResponseModel(code=400, message="Only estimated orders can be billed", error={})

    order = await order_svc.bill_order(
        db, order, bill_number=body.bill_number, notes=body.notes
    )
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Order billed")


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
    if order.status != OrderStatus.billed:
        return ErrorResponseModel(code=400, message="Discounts only on billed orders", error={})
    order = await order_svc.apply_discount(
        db, order,
        discount_percent=discount_in.discount_percent,
        discount_flat=discount_in.discount_flat,
        notes=discount_in.notes,
    )
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Discount applied")


# ── Warehouse ──────────────────────────────────────────────────────────────────

@router.patch("/{order_id}/packing", response_model=CommonResponse)
async def move_to_packing(
    order_id: uuid.UUID,
    body: OrderNoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status != OrderStatus.billed:
        return ErrorResponseModel(code=400, message="Only billed orders can move to packing", error={})
    order = await order_svc.move_to_packing(db, order, notes=body.notes)
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
        tracking_link=dispatch_in.tracking_link,
        delivery_notes=dispatch_in.delivery_notes,
        dispatched_box_count=dispatch_in.dispatched_box_count,
        notes=dispatch_in.notes,
    )
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Order dispatched")


@router.patch("/{order_id}/deliver", response_model=CommonResponse)
async def deliver_order(
    order_id: uuid.UUID,
    body: OrderNoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status != OrderStatus.dispatched:
        return ErrorResponseModel(code=400, message="Only dispatched orders can be delivered", error={})
    order = await order_svc.deliver_order(db, order, notes=body.notes)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Order delivered")


@router.patch("/{order_id}/delivered-at", response_model=CommonResponse)
async def update_delivered_at(
    order_id: uuid.UUID,
    body: UpdateDeliveredAtInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status != OrderStatus.delivered:
        return ErrorResponseModel(code=400, message="Only delivered orders can update delivery date", error={})
    order = await order_svc.update_delivered_at(db, order, body.delivered_at, notes=body.notes)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order.id)
    return ResponseModel(data=order_svc.serialize_order(order), message="Delivery date updated")


# ── Returns ────────────────────────────────────────────────────────────────────

@router.post("/{order_id}/returns", response_model=CommonResponse)
async def process_return(
    order_id: uuid.UUID,
    return_in: CreateOrderReturnInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    if order.status not in (OrderStatus.delivered, OrderStatus.partially_returned):
        return ErrorResponseModel(
            code=400, message="Only delivered or partially returned orders can have returns", error={}
        )
    if not return_in.items:
        return ErrorResponseModel(code=400, message="No items provided for return", error={})
    returns = await order_svc.process_return(db, order, return_in, processed_by=current_user.id)
    await db.commit()
    order = await order_svc.get_order_by_id(db, order_id)
    return ResponseModel(
        data={
            "order": order_svc.serialize_order(order),
            "returns": [order_svc.serialize_order_return(r) for r in returns],
        },
        message="Return processed and stock restored"
    )


@router.get("/{order_id}/returns", response_model=CommonResponse)
async def get_order_returns(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    returns = await order_svc.get_returns_for_order(db, order_id)
    return ResponseModel(
        data=[order_svc.serialize_order_return(r) for r in returns],
        message="Order returns fetched"
    )


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
    if order.status not in (OrderStatus.placed, OrderStatus.rejected, OrderStatus.cancelled):
        return ErrorResponseModel(
            code=400, message="Only placed, rejected or cancelled orders can be deleted", error={}
        )
    await order_svc.soft_delete_order(db, order)
    await db.commit()
    return ResponseModel(data=None, message="Order deleted")


@router.get("/{order_id}/hierarchy", response_model=CommonResponse)
async def get_order_hierarchy(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns the complete parent → child → grandchild tree for any order in the chain.

    Pass any order ID in the chain (A, B, or C) and you'll get the full tree
    rooted at the topmost ancestor, plus aggregate totals across all orders.
    """
    result = await order_svc.get_order_hierarchy(db, order_id)
    if result is None:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    return ResponseModel(data=result, message="Order hierarchy fetched")


@router.get("/{order_id}/invoice")
async def order_invoice(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await order_svc.get_order_by_id(db, order_id)
    if not order:
        return ErrorResponseModel(code=404, message="Order not found", error={})
    data = order_svc.serialize_order(order)
    pdf = build_invoice_pdf(data)
    return pdf_response(pdf, f"invoice_{data['orderNumber']}")

