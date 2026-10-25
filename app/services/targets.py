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
        # Revive a previously soft-deleted target. The lookup intentionally ignores
        # is_deleted (the unique constraint spans user+tenant+year+month+type+category,
        # so a dead row still blocks a fresh insert); without this, re-adding a target
        # that was once deleted would update the dead row but leave it hidden.
        existing.is_deleted = False
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
    tenant_id: Optional[uuid.UUID] = None,
) -> List[ExecutiveTarget]:
    filters = [
        ExecutiveTarget.user_id == user_id,
        ExecutiveTarget.is_deleted == False,  # noqa
        ExecutiveTarget.year == year,
        ExecutiveTarget.month == month,
    ]
    if tenant_id:
        filters.append(ExecutiveTarget.tenant_id == tenant_id)
    result = await db.execute(
        select(ExecutiveTarget)
        .where(*filters)
        .options(selectinload(ExecutiveTarget.category))
        .order_by(ExecutiveTarget.target_type)
    )
    return result.scalars().all()


async def get_achievement_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
    year: int,
    month: int,
    tenant_id: Optional[uuid.UUID] = None,
    statuses: Optional[List[OrderStatus]] = None,
) -> dict:
    """Achievement vs targets for an executive in a month.

    Scoped to `tenant_id` when given (targets are set per tenant, so the admin Targets
    page must compare a tenant's orders against that tenant's targets). Handles all five
    target types: order_count / order_value / order_pieces (overall) and
    category_quantity / category_value (per category).

    `statuses`: when given, only orders in those statuses count toward the achieved figures
    (so the executive can see achievement for e.g. just `delivered` or `billed`). When not
    given, rejected / returned / cancelled orders are excluded and everything else counts.

    Order COUNT counts root arrivals only (split children don't inflate it); order VALUE,
    PIECES and category figures INCLUDE split children, since their moved-out value belongs
    to this executive (parent + children = the original order's total).
    """
    excluded = [OrderStatus.rejected, OrderStatus.returned, OrderStatus.cancelled]

    scope = [
        Order.assigned_executive == user_id,
        Order.is_deleted == False,  # noqa
        extract("year", Order.created_at) == year,
        extract("month", Order.created_at) == month,
    ]
    # Chosen statuses override the default exclusion; otherwise drop the non-sale ones.
    if statuses:
        scope.append(Order.status.in_(statuses))
    else:
        scope.append(Order.status.not_in(excluded))
    if tenant_id:
        scope.append(Order.tenant_id == tenant_id)

    # value / pieces / category include split children; count uses roots only.
    metric_filters = scope
    count_filters = [*scope, Order.parent_order_id == None]  # noqa

    order_count = int((await db.execute(
        select(func.count(Order.id)).where(*count_filters)
    )).scalar() or 0)

    order_value = float((await db.execute(
        select(func.coalesce(func.sum(Order.total_amount), 0)).where(*metric_filters)
    )).scalar() or 0)

    order_pieces = int((await db.execute(
        select(func.coalesce(func.sum(OrderItem.count), 0))
        .select_from(OrderItem).join(Order, Order.id == OrderItem.order_id)
        .where(*metric_filters)
    )).scalar() or 0)

    # Pieces AND value sold per category (one query).
    cat_rows = (await db.execute(
        select(
            Product.category_id,
            func.coalesce(func.sum(OrderItem.count), 0),
            func.coalesce(func.sum(OrderItem.total_price), 0),
        )
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Product, Product.id == OrderItem.product_id)
        .where(*metric_filters)
        .group_by(Product.category_id)
    )).all()
    cat_qty_map = {str(cid): int(q) for cid, q, v in cat_rows}
    cat_val_map = {str(cid): float(v) for cid, q, v in cat_rows}

    # ── Targets (tenant-scoped when tenant_id given) ───────────────────────────
    tfilters = [
        ExecutiveTarget.user_id == user_id,
        ExecutiveTarget.is_deleted == False,  # noqa
        ExecutiveTarget.year == year,
        ExecutiveTarget.month == month,
    ]
    if tenant_id:
        tfilters.append(ExecutiveTarget.tenant_id == tenant_id)
    targets = (await db.execute(
        select(ExecutiveTarget).where(*tfilters).options(selectinload(ExecutiveTarget.category))
    )).scalars().all()

    def _pct(achieved, target):
        return round(achieved / target * 100, 2) if target else None

    # Overall targets — summed by type (sums across tenants when tenant_id is None).
    overall_val: dict = {}
    overall_meta: dict = {}
    cat_acc: dict = {}
    for t in targets:
        if t.category_id is None:
            overall_val[t.target_type] = overall_val.get(t.target_type, 0.0) + float(t.target_value)
            overall_meta.setdefault(t.target_type, (str(t.id), t.notes))
        else:
            cid = str(t.category_id)
            e = cat_acc.setdefault(cid, {
                "categoryId": cid,
                "categoryName": t.category.name if t.category else None,
                "quantityTarget": None, "valueTarget": None, "notes": t.notes,
            })
            if t.target_type == TargetType.category_quantity:
                e["quantityTarget"] = (e["quantityTarget"] or 0.0) + float(t.target_value)
            elif t.target_type == TargetType.category_value:
                e["valueTarget"] = (e["valueTarget"] or 0.0) + float(t.target_value)

    def _overall(ttype, achieved):
        # Always return the object (never null) so the ORDERS / VALUE / PIECES columns
        # show the achieved value even when no target is set — no frontend change needed.
        # When there's no target: target=0, percentage=None (frontend shows achieved / 0).
        if ttype in overall_val:
            tv = overall_val[ttype]
            tid, notes = overall_meta.get(ttype, (None, None))
            pct = _pct(achieved, tv)
            return {"targetId": tid, "target": tv, "achieved": float(achieved),
                    "percentage": pct if pct is not None else 0, "notes": notes}
        # percentage must be a number (frontend expects `number`, not null — null crashes
        # it). 0 when there's no target; the cell shows "achieved / 0".
        return {"targetId": "", "target": 0, "achieved": float(achieved),
                "percentage": 0, "notes": None}

    category_targets = []
    for cid, e in cat_acc.items():
        q_ach = cat_qty_map.get(cid, 0)
        v_ach = round(cat_val_map.get(cid, 0.0), 2)
        qt, vt = e["quantityTarget"], e["valueTarget"]
        category_targets.append({
            "categoryId": cid,
            "categoryName": e["categoryName"],
            "quantityTarget": qt,
            "quantityAchieved": q_ach,
            "quantityPercentage": _pct(q_ach, qt),
            "valueTarget": vt,
            "valueAchieved": v_ach,
            "valuePercentage": _pct(v_ach, vt),
            "notes": e["notes"],
            # legacy quantity-based fields (kept for backward compatibility)
            "target": qt,
            "achieved": float(q_ach),
            "percentage": _pct(q_ach, qt) or 0,
        })

    return {
        "userId": str(user_id),
        "tenantId": str(tenant_id) if tenant_id else None,
        "year": year,
        "month": month,
        "orderCount": _overall(TargetType.order_count, order_count),
        "orderValue": _overall(TargetType.order_value, order_value),
        "orderPieces": _overall(TargetType.order_pieces, order_pieces),
        "categoryTargets": category_targets,  # one entry per category (quantity and/or value)
    }


async def get_all_executives_summary(
    db: AsyncSession,
    year: int,
    month: int,
    tenant_id: Optional[uuid.UUID] = None,
    statuses: Optional[List[OrderStatus]] = None,
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
        summary = await get_achievement_summary(db, exe.id, year, month, tenant_id, statuses)
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