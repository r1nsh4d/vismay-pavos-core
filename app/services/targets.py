import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.target import ExecutiveTarget, TargetType
from app.models.order import Order, OrderStatus, OrderType
from app.models.order import OrderItem
from app.models.product import Product
from app.schemas.target import TargetCreate
from app.core.exceptions import AppException


async def set_target(db: AsyncSession, target_in: TargetCreate) -> ExecutiveTarget:
    # Category targets (pieces or value) require a category_id
    if target_in.target_type in (TargetType.category_quantity, TargetType.category_value) and not target_in.category_id:
        raise AppException(
            status_code=400,
            detail="category_id is required for category targets"
        )

    # Check existing — match on tenant + category too (upsert per tenant/category)
    existing = await db.scalar(
        select(ExecutiveTarget).where(
            ExecutiveTarget.user_id == target_in.user_id,
            ExecutiveTarget.tenant_id == target_in.tenant_id,
            ExecutiveTarget.year == target_in.year,
            ExecutiveTarget.month == target_in.month,
            ExecutiveTarget.target_type == target_in.target_type,
            ExecutiveTarget.category_id == target_in.category_id,
        )
    )
    if existing:
        existing.target_value = target_in.target_value
        existing.notes = target_in.notes
        await db.flush()
        return existing

    target = ExecutiveTarget(**target_in.model_dump())
    db.add(target)
    await db.flush()

    # Reload with category
    result = await db.execute(
        select(ExecutiveTarget)
        .where(ExecutiveTarget.id == target.id)
        .options(selectinload(ExecutiveTarget.category))
    )
    return result.scalar_one()


async def get_targets_by_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    year: int,
    month: int,
) -> List[ExecutiveTarget]:
    result = await db.execute(
        select(ExecutiveTarget)
        .where(
            ExecutiveTarget.user_id == user_id,
            ExecutiveTarget.year == year,
            ExecutiveTarget.month == month,
        )
        .options(selectinload(ExecutiveTarget.category))
        .order_by(ExecutiveTarget.target_type)
    )
    return result.scalars().all()


async def get_achievement_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
    year: int,
    month: int,
) -> dict:
    excluded = [OrderStatus.rejected, OrderStatus.returned, OrderStatus.cancelled]

    base_filters = [
        Order.assigned_executive == user_id,
        Order.is_deleted == False,  # noqa
        Order.status.not_in(excluded),
        Order.parent_order_id == None,  # noqa
        extract("year", Order.created_at) == year,
        extract("month", Order.created_at) == month,
    ]

    # ── Order count ────────────────────────────────────────────────────────────
    order_count = (await db.execute(
        select(func.count(Order.id)).where(*base_filters)
    )).scalar() or 0

    # ── Order value ────────────────────────────────────────────────────────────
    order_value = float((await db.execute(
        select(func.coalesce(func.sum(Order.total_amount), 0)).where(*base_filters)
    )).scalar() or 0)

    # ── Category quantity — pieces sold per category ───────────────────────────
    # Sum order item counts grouped by category
    category_qty_result = await db.execute(
        select(
            Product.category_id,
            func.sum(OrderItem.count).label("total_qty"),
        )
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(*base_filters)
        .group_by(Product.category_id)
    )
    category_qty_map = {
        str(row.category_id): int(row.total_qty)
        for row in category_qty_result.all()
    }

    # ── Fetch targets ──────────────────────────────────────────────────────────
    targets = await get_targets_by_user(db, user_id, year, month)

    # Build results
    order_count_target = None
    order_value_target = None
    category_targets = []

    for t in targets:
        if t.target_type == TargetType.order_count:
            achieved = float(order_count)
            pct = round((achieved / float(t.target_value)) * 100, 2) if t.target_value else 0
            order_count_target = {
                "targetId": str(t.id),
                "target": float(t.target_value),
                "achieved": achieved,
                "percentage": pct,
                "notes": t.notes,
            }

        elif t.target_type == TargetType.order_value:
            achieved = order_value
            pct = round((achieved / float(t.target_value)) * 100, 2) if t.target_value else 0
            order_value_target = {
                "targetId": str(t.id),
                "target": float(t.target_value),
                "achieved": achieved,
                "percentage": pct,
                "notes": t.notes,
            }

        elif t.target_type == TargetType.category_quantity:
            achieved = float(category_qty_map.get(str(t.category_id), 0))
            pct = round((achieved / float(t.target_value)) * 100, 2) if t.target_value else 0
            category_targets.append({
                "targetId": str(t.id),
                "categoryId": str(t.category_id),
                "categoryName": t.category.name if t.category else None,
                "target": float(t.target_value),
                "achieved": achieved,
                "percentage": pct,
                "notes": t.notes,
            })

    return {
        "userId": str(user_id),
        "year": year,
        "month": month,
        "orderCount": order_count_target,
        "orderValue": order_value_target,
        "categoryTargets": category_targets,  # ← list, one per category
    }


async def get_all_executives_summary(
    db: AsyncSession,
    year: int,
    month: int,
    tenant_id: Optional[uuid.UUID] = None,
) -> list[dict]:
    """Get achievement summary for all executives — for admin view."""
    from app.models.user import User
    from app.models.role import Role

    exec_query = (
        select(User)
        .where(User.is_deleted == False, User.is_active == True)
        .join(User.role)
        .where(Role.name == "executive")
    )
    if tenant_id:
        from app.models.user import UserTenant
        exec_query = exec_query.where(
            User.user_tenants.any(UserTenant.tenant_id == tenant_id)
        )

    result = await db.execute(exec_query)
    executives = result.scalars().all()

    summaries = []
    for exe in executives:
        summary = await get_achievement_summary(db, exe.id, year, month)
        summary["executiveName"] = f"{exe.first_name} {exe.last_name}".strip()
        summary["username"] = exe.username
        summaries.append(summary)

    return summaries


async def delete_target(db: AsyncSession, user_id: uuid.UUID, target_id: uuid.UUID) -> bool:
    target = await db.scalar(
        select(ExecutiveTarget).where(
            ExecutiveTarget.id == target_id,
            ExecutiveTarget.user_id == user_id,
        )
    )
    if not target:
        return False
    target.is_deleted = True
    await db.flush()
    return True


def serialize_target(t: ExecutiveTarget) -> dict:
    return {
        "id": str(t.id),
        "userId": str(t.user_id),
        "tenantId": str(t.tenant_id),
        "year": t.year,
        "month": t.month,
        "targetType": t.target_type,
        "targetValue": float(t.target_value),
        "categoryId": str(t.category_id) if t.category_id else None,
        "categoryName": t.category.name if t.category else None,
        "notes": t.notes,
    }