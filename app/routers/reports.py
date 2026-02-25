from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product
from app.models.stock import Stock
from app.models.user import User
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/stock-summary")
async def stock_summary_report(
    tenant_id: int = Query(...),
    category_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Stock in/out summary per product"""
    query = (
        select(
            Product.id.label("product_id"),
            Product.name.label("product_name"),
            func.sum(Stock.boxes_total).label("total_in"),
            func.sum(Stock.boxes_available).label("available"),
            func.sum(Stock.boxes_reserved).label("reserved"),
            func.sum(Stock.boxes_dispatched).label("dispatched"),
        )
        .join(Stock, Stock.product_id == Product.id)
        .where(Stock.tenant_id == tenant_id, Stock.is_active == True)
        .group_by(Product.id, Product.name)
    )
    if category_id:
        query = query.where(Product.category_id == category_id)

    result = await db.execute(query)
    data = [
        {
            "product_id": r.product_id,
            "product_name": r.product_name,
            "total_in": r.total_in or 0,
            "available": r.available or 0,
            "reserved": r.reserved or 0,
            "dispatched": r.dispatched or 0,
        }
        for r in result.all()
    ]
    return ResponseModel(data=data, message="Stock summary fetched")


@router.get("/low-stock")
async def low_stock_alert(
    tenant_id: int = Query(...),
    threshold: int = Query(5, description="Alert if available boxes below this"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Products with available stock below threshold"""
    result = await db.execute(
        select(
            Product.id.label("product_id"),
            Product.name.label("product_name"),
            func.sum(Stock.boxes_available).label("boxes_available"),
        )
        .join(Stock, Stock.product_id == Product.id)
        .where(Stock.tenant_id == tenant_id, Stock.is_active == True)
        .group_by(Product.id, Product.name)
        .having(func.sum(Stock.boxes_available) < threshold)
        .order_by(func.sum(Stock.boxes_available).asc())
    )
    data = [
        {
            "product_id": r.product_id,
            "product_name": r.product_name,
            "boxes_available": r.boxes_available or 0,
        }
        for r in result.all()
    ]
    return ResponseModel(data=data, message="Low stock products fetched")


@router.get("/orders-by-executive")
async def orders_by_executive_report(
    tenant_id: int = Query(...),
    executive_id: int | None = Query(None),
    status: OrderStatus | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    query = (
        select(
            Order.placed_by.label("executive_id"),
            User.first_name.label("first_name"),
            User.last_name.label("last_name"),
            func.count(Order.id).label("total_orders"),
            func.count(
                func.nullif(Order.status == OrderStatus.DELIVERED, False)
            ).label("delivered"),
            func.count(
                func.nullif(Order.status == OrderStatus.CANCELLED, False)
            ).label("cancelled"),
        )
        .join(User, User.id == Order.placed_by)
        .where(Order.tenant_id == tenant_id)
        .group_by(Order.placed_by, User.first_name, User.last_name)
    )
    if executive_id:
        query = query.where(Order.placed_by == executive_id)
    if status:
        query = query.where(Order.status == status)

    result = await db.execute(query)
    data = [
        {
            "executive_id": r.executive_id,
            "name": f"{r.first_name} {r.last_name or ''}".strip(),
            "total_orders": r.total_orders,
            "delivered": r.delivered,
            "cancelled": r.cancelled,
        }
        for r in result.all()
    ]
    return ResponseModel(data=data, message="Orders by executive fetched")


@router.get("/orders-by-shop")
async def orders_by_shop_report(
    tenant_id: int = Query(...),
    shop_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    query = (
        select(
            Order.shop_id,
            func.count(Order.id).label("total_orders"),
            func.sum(OrderItem.boxes_requested).label("total_boxes_requested"),
            func.sum(OrderItem.boxes_fulfilled).label("total_boxes_fulfilled"),
        )
        .join(OrderItem, OrderItem.order_id == Order.id)
        .where(Order.tenant_id == tenant_id)
        .group_by(Order.shop_id)
    )
    if shop_id:
        query = query.where(Order.shop_id == shop_id)

    result = await db.execute(query)
    data = [
        {
            "shop_id": r.shop_id,
            "total_orders": r.total_orders,
            "total_boxes_requested": r.total_boxes_requested or 0,
            "total_boxes_fulfilled": r.total_boxes_fulfilled or 0,
        }
        for r in result.all()
    ]
    return ResponseModel(data=data, message="Orders by shop fetched")


@router.get("/sales-by-category")
async def sales_by_category_report(
    tenant_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(
        select(
            Order.category_id,
            func.count(Order.id).label("total_orders"),
            func.sum(OrderItem.boxes_fulfilled).label("boxes_fulfilled"),
        )
        .join(OrderItem, OrderItem.order_id == Order.id)
        .where(
            Order.tenant_id == tenant_id,
            Order.status == OrderStatus.DELIVERED,
        )
        .group_by(Order.category_id)
    )
    data = [
        {
            "category_id": r.category_id,
            "total_orders": r.total_orders,
            "boxes_fulfilled": r.boxes_fulfilled or 0,
        }
        for r in result.all()
    ]
    return ResponseModel(data=data, message="Sales by category fetched")