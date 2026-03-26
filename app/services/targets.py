import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.target import ExecutiveTarget, TargetType
from app.models.order import Order, OrderStatus
from app.schemas.target import TargetCreate
from app.core.exceptions import AppException


async def set_target(db: AsyncSession, target_in: TargetCreate) -> ExecutiveTarget:
    existing = await db.scalar(
        select(ExecutiveTarget).where(
            ExecutiveTarget.user_id == target_in.user_id,
            ExecutiveTarget.year == target_in.year,
            ExecutiveTarget.month == target_in.month,
            ExecutiveTarget.target_type == target_in.target_type,
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
    return target


async def get_targets_by_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    year: int,
    month: int,
) -> List[ExecutiveTarget]:
    result = await db.execute(
        select(ExecutiveTarget).where(
            ExecutiveTarget.user_id == user_id,
            ExecutiveTarget.year == year,
            ExecutiveTarget.month == month,
        )
    )
    return result.scalars().all()


async def get_achievement_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
    year: int,
    month: int,
) -> dict:
    excluded = [OrderStatus.rejected, OrderStatus.returned]

    # Order count for this executive this month
    order_count = (await db.execute(
        select(func.count()).select_from(
            select(Order).where(
                Order.assigned_executive == user_id,
                Order.is_deleted == False,
                Order.status.not_in(excluded),
                Order.parent_order_id == None,  # noqa — only parent orders
                extract("year", Order.created_at) == year,
                extract("month", Order.created_at) == month,
            ).subquery()
        )
    )).scalar() or 0

    # Total order value for this executive this month
    order_value = float((await db.execute(
        select(func.coalesce(func.sum(Order.total_amount), 0)).where(
            Order.assigned_executive == user_id,
            Order.is_deleted == False,
            Order.status.not_in(excluded),
            Order.parent_order_id == None,  # noqa
            extract("year", Order.created_at) == year,
            extract("month", Order.created_at) == month,
        )
    )).scalar() or 0)

    # Fetch targets
    targets = await get_targets_by_user(db, user_id, year, month)
    target_map = {t.target_type: t for t in targets}

    def build_achievement(target_type: TargetType, achieved: float) -> dict:
        t = target_map.get(target_type)
        if not t:
            return {"target": None, "achieved": achieved, "percentage": None}
        pct = round((achieved / float(t.target_value)) * 100, 2) if t.target_value else 0
        return {
            "target": float(t.target_value),
            "achieved": achieved,
            "percentage": pct,
            "notes": t.notes,
        }

    return {
        "userId": str(user_id),
        "year": year,
        "month": month,
        "orderCount": build_achievement(TargetType.order_count, float(order_count)),
        "orderValue": build_achievement(TargetType.order_value, order_value),
    }


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
