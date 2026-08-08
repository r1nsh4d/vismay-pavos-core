"""Read-only dashboard / map / live-status queries for the admin UI.

Everything here is SELECT-only — no writes, no schema changes — safe for production.
Visualisation (charts, Google Map) is the frontend's job; these just serve data.
"""
import uuid
from datetime import datetime, date, time, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.models.order import Order, OrderItem, OrderStatus
from app.models.user import User
from app.models.role import Role
from app.models.shop import Shop
from app.models.product import Product
from app.models.category import Category
from app.models.district import District
from app.models.tenant import Tenant
from app.models.attendance import WorkLog, ShopVisit


# ── Order dashboard ──────────────────────────────────────────────────────────────

async def get_order_dashboard(
    db: AsyncSession,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    status: Optional[OrderStatus] = None,
    tenant_id: Optional[uuid.UUID] = None,
) -> dict:
    """Order counts / value / pieces for a date range, broken down by status and by day.

    Date range is inclusive on order `created_at`. A single date (date_from == date_to)
    gives one day; omit both for all-time. `status` narrows every figure to that status.
    """
    filters = [Order.is_deleted == False]  # noqa
    if date_from:
        filters.append(Order.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        filters.append(Order.created_at <= datetime.combine(date_to, time.max))
    if status:
        filters.append(Order.status == status)
    if tenant_id:
        filters.append(Order.tenant_id == tenant_id)

    total_orders, total_value = (await db.execute(
        select(func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0)).where(*filters)
    )).one()

    total_pieces = (await db.execute(
        select(func.coalesce(func.sum(OrderItem.count), 0))
        .select_from(OrderItem).join(Order, OrderItem.order_id == Order.id).where(*filters)
    )).scalar() or 0

    by_status = [
        {"status": s.value, "count": c, "value": round(float(v), 2)}
        for s, c, v in (await db.execute(
            select(Order.status, func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0))
            .where(*filters).group_by(Order.status)
        )).all()
    ]

    day_col = func.date(Order.created_at)
    by_day = [
        {"date": str(d), "count": c, "value": round(float(v), 2)}
        for d, c, v in (await db.execute(
            select(day_col.label("d"), func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0))
            .where(*filters).group_by(day_col).order_by(day_col)
        )).all()
    ]

    return {
        "dateFrom": str(date_from) if date_from else None,
        "dateTo": str(date_to) if date_to else None,
        "status": status.value if status else None,
        "totalOrders": total_orders,
        "totalValue": round(float(total_value), 2),
        "totalPieces": int(total_pieces),
        "byStatus": by_status,
        "byDay": by_day,
    }


# ── Map: shops with coordinates ──────────────────────────────────────────────────

async def get_map_shops(
    db: AsyncSession,
    district_id: Optional[uuid.UUID] = None,
    is_active: Optional[bool] = None,
) -> list[dict]:
    """Shops that have coordinates, for plotting on a map. Shops without lat/lng are skipped."""
    query = (
        select(Shop)
        .where(Shop.is_deleted == False)  # noqa
        .options(selectinload(Shop.district), selectinload(Shop.taluk))
    )
    if district_id:
        query = query.where(Shop.district_id == district_id)
    if is_active is not None:
        query = query.where(Shop.is_active == is_active)

    shops = (await db.execute(query)).scalars().unique().all()

    result = []
    for s in shops:
        addr = s.address or {}
        lat, lng = addr.get("latitude"), addr.get("longitude")
        if lat is None or lng is None:
            continue  # no coordinates → nothing to plot
        result.append({
            "id": str(s.id),
            "name": s.name,
            "latitude": float(lat),
            "longitude": float(lng),
            "district": s.district.name if s.district else None,
            "taluk": s.taluk.name if s.taluk else None,
            "contactPerson": s.contact_person,
            "phone": s.phone,
            "isActive": s.is_active,
            "isEbo": s.is_ebo,
        })
    return result


# ── Live executive status / location ─────────────────────────────────────────────

async def get_executive_status_list(
    db: AsyncSession,
    user_id: Optional[uuid.UUID] = None,
) -> list[dict]:
    """Current status + latest location of executives (today).

    status: not_checked_in | working | in_shop | checked_out
      - not_checked_in : no check-in today
      - working        : checked in, currently travelling (not inside a shop)
      - in_shop        : checked in and currently inside a shop (open shop visit)
      - checked_out    : finished the day
    Location is the latest GPS ping today (or the checkout point once checked out).
    """
    today = datetime.now(timezone.utc).date()

    exec_query = (
        select(User)
        .join(User.role)
        .where(
            User.is_deleted == False,  # noqa
            User.is_active == True,    # noqa
            Role.name == "executive",
        )
    )
    if user_id:
        exec_query = exec_query.where(User.id == user_id)

    executives = (await db.execute(exec_query)).scalars().unique().all()
    if not executives:
        return []

    exec_ids = [e.id for e in executives]

    logs = (await db.execute(
        select(WorkLog)
        .where(
            WorkLog.user_id.in_(exec_ids),
            WorkLog.work_date == today,
            WorkLog.is_deleted == False,  # noqa
        )
        .options(
            selectinload(WorkLog.location_events),
            selectinload(WorkLog.shop_visits).selectinload(ShopVisit.shop),
        )
    )).scalars().unique().all()
    logs_by_user = {l.user_id: l for l in logs}

    result = []
    for e in executives:
        log = logs_by_user.get(e.id)
        status = "not_checked_in"
        current_shop = None
        lat = lng = last_updated = None

        if log and log.checkin_at:
            if log.checkout_at:
                status = "checked_out"
                lat = float(log.checkout_lat) if log.checkout_lat is not None else None
                lng = float(log.checkout_lng) if log.checkout_lng is not None else None
                last_updated = log.checkout_at.isoformat()
            else:
                open_visits = [v for v in log.shop_visits if v.exit_at is None]
                if open_visits:
                    status = "in_shop"
                    current_shop = open_visits[0].shop.name if open_visits[0].shop else None
                else:
                    status = "working"
                if log.location_events:
                    latest = max(log.location_events, key=lambda x: x.recorded_at)
                    lat = float(latest.latitude)
                    lng = float(latest.longitude)
                    last_updated = latest.recorded_at.isoformat()

        result.append({
            "userId": str(e.id),
            "name": f"{e.first_name} {e.last_name or ''}".strip(),
            "phone": e.phone,
            "status": status,
            "currentShop": current_shop,
            "latitude": lat,
            "longitude": lng,
            "lastUpdated": last_updated,
            "checkinAt": log.checkin_at.isoformat() if log and log.checkin_at else None,
            "checkoutAt": log.checkout_at.isoformat() if log and log.checkout_at else None,
            "shopsVisitedToday": (log.total_shops_visited or 0) if log else 0,
            "distanceKmToday": float(log.total_distance_km) if (log and log.total_distance_km) else 0,
        })
    return result


# ── BI / analytics (read-only) ───────────────────────────────────────────────────

def _created_between(date_from: Optional[date], date_to: Optional[date]) -> list:
    f = []
    if date_from:
        f.append(Order.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        f.append(Order.created_at <= datetime.combine(date_to, time.max))
    return f


async def _totals(db: AsyncSession, date_from, date_to, tenant_id=None) -> dict:
    filters = [Order.is_deleted == False, *_created_between(date_from, date_to)]  # noqa
    if tenant_id:
        filters.append(Order.tenant_id == tenant_id)
    orders, value = (await db.execute(
        select(func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0)).where(*filters)
    )).one()
    pieces = (await db.execute(
        select(func.coalesce(func.sum(OrderItem.count), 0))
        .select_from(OrderItem).join(Order, OrderItem.order_id == Order.id).where(*filters)
    )).scalar() or 0
    return {"orders": orders, "value": round(float(value), 2), "pieces": int(pieces)}


async def get_top_products(
    db: AsyncSession, date_from, date_to, tenant_id=None, limit: int = 10,
) -> list[dict]:
    """Top products by order value (with pieces) in the range."""
    filters = [Order.is_deleted == False, *_created_between(date_from, date_to)]  # noqa
    if tenant_id:
        filters.append(Order.tenant_id == tenant_id)
    value = func.coalesce(func.sum(OrderItem.total_price), 0)
    rows = (await db.execute(
        select(
            Product.id, Product.name, Category.name.label("category"),
            func.coalesce(func.sum(OrderItem.count), 0), value,
        )
        .select_from(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Product, OrderItem.product_id == Product.id)
        .join(Category, Product.category_id == Category.id, isouter=True)
        .where(*filters)
        .group_by(Product.id, Product.name, Category.name)
        .order_by(value.desc())
        .limit(limit)
    )).all()
    return [
        {"productId": str(pid), "productName": name, "category": cat,
         "pieces": int(pieces), "value": round(float(val), 2)}
        for pid, name, cat, pieces, val in rows
    ]


async def get_executive_performance(
    db: AsyncSession, date_from, date_to, tenant_id=None,
) -> list[dict]:
    """Per-executive orders / value / delivered / pieces over a date range (parent orders only)."""
    filters = [
        Order.is_deleted == False,          # noqa
        Order.assigned_executive.isnot(None),
        Order.parent_order_id == None,       # noqa
        *_created_between(date_from, date_to),
    ]
    if tenant_id:
        filters.append(Order.tenant_id == tenant_id)

    order_rows = (await db.execute(
        select(
            Order.assigned_executive,
            func.count(Order.id),
            func.coalesce(func.sum(Order.total_amount), 0),
            func.coalesce(func.sum(case((Order.status == OrderStatus.delivered, 1), else_=0)), 0),
        ).where(*filters).group_by(Order.assigned_executive)
    )).all()

    piece_rows = (await db.execute(
        select(Order.assigned_executive, func.coalesce(func.sum(OrderItem.count), 0))
        .select_from(OrderItem).join(Order, OrderItem.order_id == Order.id)
        .where(*filters).group_by(Order.assigned_executive)
    )).all()
    pieces_by = {eid: int(p) for eid, p in piece_rows}

    exec_ids = [eid for eid, *_ in order_rows]
    names = {}
    if exec_ids:
        users = (await db.execute(select(User).where(User.id.in_(exec_ids)))).scalars().all()
        names = {u.id: f"{u.first_name} {u.last_name or ''}".strip() for u in users}

    result = [
        {
            "userId": str(eid),
            "name": names.get(eid, ""),
            "totalOrders": int(cnt),
            "totalValue": round(float(val), 2),
            "deliveredOrders": int(delivered),
            "totalPieces": pieces_by.get(eid, 0),
        }
        for eid, cnt, val, delivered in order_rows
    ]
    result.sort(key=lambda r: r["totalValue"], reverse=True)
    return result


async def get_breakdown(
    db: AsyncSession, by: str, date_from, date_to, tenant_id=None, limit: int = 50,
) -> list[dict]:
    """Sales grouped by a dimension: district | shop | tenant | category.

    value = sum of line-item totals (gross), orders = distinct orders, pieces = total pieces.
    """
    filters = [Order.is_deleted == False, *_created_between(date_from, date_to)]  # noqa
    if tenant_id:
        filters.append(Order.tenant_id == tenant_id)

    orders = func.count(func.distinct(Order.id)).label("orders")
    value = func.coalesce(func.sum(OrderItem.total_price), 0).label("value")
    pieces = func.coalesce(func.sum(OrderItem.count), 0).label("pieces")

    dims = {
        "district": (District.name, [(Shop, Order.shop_id == Shop.id),
                                     (District, Shop.district_id == District.id)]),
        "shop": (Shop.name, [(Shop, Order.shop_id == Shop.id)]),
        "tenant": (Tenant.name, [(Tenant, Order.tenant_id == Tenant.id)]),
        "category": (Category.name, [(Product, OrderItem.product_id == Product.id),
                                     (Category, Product.category_id == Category.id)]),
    }
    if by not in dims:
        raise AppException(status_code=400, detail="by must be one of: district, shop, tenant, category")
    label_col, joins = dims[by]

    q = (
        select(label_col.label("label"), orders, value, pieces)
        .select_from(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
    )
    for target, onclause in joins:
        q = q.join(target, onclause)
    q = q.where(*filters).group_by(label_col).order_by(value.desc()).limit(limit)

    return [
        {"label": lbl, "orders": int(o), "value": round(float(v), 2), "pieces": int(p)}
        for lbl, o, v, p in (await db.execute(q)).all()
    ]


async def get_trend(
    db: AsyncSession, group: str, date_from, date_to, tenant_id=None,
) -> list[dict]:
    """Order count + value over time, grouped by day | week | month."""
    filters = [Order.is_deleted == False, *_created_between(date_from, date_to)]  # noqa
    if tenant_id:
        filters.append(Order.tenant_id == tenant_id)

    if group == "day":
        period = func.date(Order.created_at)
    elif group == "week":
        period = func.date_trunc("week", Order.created_at)
    elif group == "month":
        period = func.date_trunc("month", Order.created_at)
    else:
        raise AppException(status_code=400, detail="group must be one of: day, week, month")

    rows = (await db.execute(
        select(period.label("p"), func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0))
        .where(*filters).group_by(period).order_by(period)
    )).all()
    return [{"period": str(p)[:10], "orders": c, "value": round(float(v), 2)} for p, c, v in rows]


async def get_period_comparison(
    db: AsyncSession, date_from: date, date_to: date, tenant_id=None,
) -> dict:
    """Current range vs the immediately preceding range of the same length, with % change."""
    span = (date_to - date_from).days + 1
    prev_to = date_from - timedelta(days=1)
    prev_from = prev_to - timedelta(days=span - 1)

    current = await _totals(db, date_from, date_to, tenant_id)
    previous = await _totals(db, prev_from, prev_to, tenant_id)

    def pct(cur, prev):
        return round((cur - prev) / prev * 100, 2) if prev else None

    return {
        "current": {"dateFrom": str(date_from), "dateTo": str(date_to), **current},
        "previous": {"dateFrom": str(prev_from), "dateTo": str(prev_to), **previous},
        "change": {
            "ordersPct": pct(current["orders"], previous["orders"]),
            "valuePct": pct(current["value"], previous["value"]),
            "piecesPct": pct(current["pieces"], previous["pieces"]),
        },
    }
