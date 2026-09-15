"""Read-only dashboard / map / live-status queries for the admin UI.

Everything here is SELECT-only — no writes, no schema changes — safe for production.
Visualisation (charts, Google Map) is the frontend's job; these just serve data.
"""
import uuid
from datetime import datetime, date, time, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func, case, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.models.order import Order, OrderItem, OrderStatus
from app.models.user import User, UserDistrict
from app.models.role import Role
from app.models.target import ExecutiveTarget, TargetType
from app.models.shop import Shop
from app.models.product import Product
from app.models.category import Category
from app.models.district import District
from app.models.tenant import Tenant
from app.models.attendance import WorkLog, ShopVisit, LocationEvent, LocationEventType


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


async def get_attendance_overview(db: AsyncSession) -> dict:
    """Today's attendance roll-up + the per-executive status list.

    `counts` powers the "N agents logged in" header; `executives[]` is the clickable list —
    click one → call GET /attendance/activity/{userId} for that agent's full activity.
    """
    execs = await get_executive_status_list(db)
    working = sum(1 for e in execs if e["status"] == "working")
    in_shop = sum(1 for e in execs if e["status"] == "in_shop")
    checked_out = sum(1 for e in execs if e["status"] == "checked_out")
    not_checked_in = sum(1 for e in execs if e["status"] == "not_checked_in")
    active_now = working + in_shop

    return {
        "counts": {
            "totalExecutives": len(execs),
            "activeNow": active_now,           # checked in and still on duty (working + in_shop)
            "working": working,                # on the move
            "inShop": in_shop,                 # currently inside a shop
            "checkedOut": checked_out,         # finished for the day
            "notCheckedIn": not_checked_in,    # never checked in today
            "checkedInToday": active_now + checked_out,  # checked in at any point today
        },
        "executives": execs,
    }


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


# ── KPI monitoring (whole-application entity metrics) ─────────────────────────────

async def _scalar(db, q) -> int:
    return (await db.execute(q)).scalar() or 0


def _months_in_range(date_from: date, date_to: date) -> list[tuple[int, int]]:
    """(year, month) pairs the date range spans — targets are set per month."""
    months, y, m = [], date_from.year, date_from.month
    while (y, m) <= (date_to.year, date_to.month):
        months.append((y, m))
        m, y = (1, y + 1) if m == 12 else (m + 1, y)
    return months


async def _category_breakdown(db: AsyncSession, group_col, filters: list) -> dict:
    """Per-entity category split: {entity_key: [{categoryId, category, pieces, value}]}.

    `group_col` is the entity column to group by (e.g. Order.assigned_executive, Order.shop_id);
    `filters` are the order filters already scoped to those entities + the date range.
    """
    rows = (await db.execute(
        select(
            group_col, Category.id, Category.name,
            func.coalesce(func.sum(OrderItem.count), 0),
            func.coalesce(func.sum(OrderItem.total_price), 0),
        )
        .select_from(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Product, OrderItem.product_id == Product.id)
        .join(Category, Product.category_id == Category.id)
        .where(*filters)
        .group_by(group_col, Category.id, Category.name)
    )).all()

    by: dict = {}
    for key, cat_id, cat_name, pieces, value in rows:
        by.setdefault(key, []).append({
            "categoryId": str(cat_id), "category": cat_name,
            "pieces": int(pieces), "value": round(float(value), 2),
        })
    for k in by:
        by[k].sort(key=lambda c: c["value"], reverse=True)
    return by


async def get_kpi_overview(db: AsyncSession, date_from, date_to, tenant_id=None) -> dict:
    """Headline counts for every entity + order/attendance metrics for the range.

    Entity counts are global (active, non-deleted); order/attendance metrics honour the
    date range (and tenant_id for orders). One call for the KPI tab's top cards.
    """
    today = datetime.now(timezone.utc).date()

    executives = await _scalar(db, select(func.count(func.distinct(User.id))).join(User.role)
                               .where(User.is_deleted == False, User.is_active == True, Role.name == "executive"))  # noqa
    distributors = await _scalar(db, select(func.count(func.distinct(User.id))).join(User.role)
                                 .where(User.is_deleted == False, User.is_active == True, Role.name == "distributor"))  # noqa

    shops_total = await _scalar(db, select(func.count(Shop.id)).where(Shop.is_deleted == False))    # noqa
    shops_active = await _scalar(db, select(func.count(Shop.id)).where(Shop.is_deleted == False, Shop.is_active == True))  # noqa
    shops_ebo = await _scalar(db, select(func.count(Shop.id)).where(Shop.is_deleted == False, Shop.is_ebo == True))  # noqa

    prod_filter = [Product.is_deleted == False]  # noqa
    cat_filter = [Category.is_deleted == False]  # noqa
    if tenant_id:
        prod_filter.append(Product.tenant_id == tenant_id)
        cat_filter.append(Category.tenant_id == tenant_id)
    products_total = await _scalar(db, select(func.count(Product.id)).where(*prod_filter))
    products_active = await _scalar(db, select(func.count(Product.id)).where(*prod_filter, Product.is_active == True))  # noqa
    categories_total = await _scalar(db, select(func.count(Category.id)).where(*cat_filter))

    totals = await _totals(db, date_from, date_to, tenant_id)
    ofilters = [Order.is_deleted == False, *_created_between(date_from, date_to)]  # noqa
    if tenant_id:
        ofilters.append(Order.tenant_id == tenant_id)
    delivered = await _scalar(db, select(func.count(Order.id)).where(*ofilters, Order.status == OrderStatus.delivered))

    checked_in = await _scalar(db, select(func.count(WorkLog.id)).where(
        WorkLog.is_deleted == False, WorkLog.work_date == today, WorkLog.checkin_at.isnot(None)))  # noqa
    active_now = await _scalar(db, select(func.count(WorkLog.id)).where(
        WorkLog.is_deleted == False, WorkLog.work_date == today,                                  # noqa
        WorkLog.checkin_at.isnot(None), WorkLog.checkout_at.is_(None)))

    return {
        "dateFrom": str(date_from), "dateTo": str(date_to),
        "executives": {"total": executives, "activeNow": active_now, "checkedInToday": checked_in},
        "distributors": {"total": distributors},
        "shops": {"total": shops_total, "active": shops_active, "ebo": shops_ebo},
        "products": {"total": products_total, "active": products_active},
        "categories": {"total": categories_total},
        "orders": {
            "total": totals["orders"], "value": totals["value"],
            "pieces": totals["pieces"], "delivered": delivered,
        },
    }


async def get_executive_kpis(db: AsyncSession, date_from, date_to, tenant_id=None) -> list[dict]:
    """Per-executive KPIs combining orders and attendance for the range."""
    exec_q = (
        select(User).join(User.role)
        .where(User.is_deleted == False, User.is_active == True, Role.name == "executive")  # noqa
        .options(selectinload(User.user_districts).selectinload(UserDistrict.district))
    )
    execs = (await db.execute(exec_q)).scalars().unique().all()
    if not execs:
        return []
    ids = [e.id for e in execs]

    ofilters = [
        Order.is_deleted == False, Order.assigned_executive.in_(ids),  # noqa
        Order.parent_order_id == None, *_created_between(date_from, date_to),  # noqa
    ]
    if tenant_id:
        ofilters.append(Order.tenant_id == tenant_id)

    order_rows = (await db.execute(
        select(
            Order.assigned_executive, func.count(Order.id),
            func.coalesce(func.sum(Order.total_amount), 0),
            func.coalesce(func.sum(case((Order.status == OrderStatus.delivered, 1), else_=0)), 0),
        ).where(*ofilters).group_by(Order.assigned_executive)
    )).all()
    orders_by = {r[0]: (int(r[1]), float(r[2]), int(r[3])) for r in order_rows}

    piece_rows = (await db.execute(
        select(Order.assigned_executive, func.coalesce(func.sum(OrderItem.count), 0))
        .select_from(OrderItem).join(Order, OrderItem.order_id == Order.id)
        .where(*ofilters).group_by(Order.assigned_executive)
    )).all()
    pieces_by = {r[0]: int(r[1]) for r in piece_rows}

    afilters = [WorkLog.is_deleted == False, WorkLog.user_id.in_(ids), WorkLog.checkin_at.isnot(None)]  # noqa
    if date_from:
        afilters.append(WorkLog.work_date >= date_from)
    if date_to:
        afilters.append(WorkLog.work_date <= date_to)
    att_rows = (await db.execute(
        select(
            WorkLog.user_id, func.count(WorkLog.id),
            func.coalesce(func.sum(WorkLog.total_distance_km), 0),
            func.coalesce(func.sum(WorkLog.total_work_minutes), 0),
            func.coalesce(func.sum(WorkLog.total_shops_visited), 0),
        ).where(*afilters).group_by(WorkLog.user_id)
    )).all()
    att_by = {r[0]: (int(r[1]), float(r[2]), int(r[3]), int(r[4])) for r in att_rows}

    # Pieces & amount split by category, per executive.
    cat_by = await _category_breakdown(db, Order.assigned_executive, ofilters)

    # Monthly targets summed over the months the range spans:
    #   order_count / order_value / order_pieces  → overall (tenant-level) targets
    #   category_quantity / category_value        → per-category piece / value targets
    targets_by: dict = {}
    cat_piece_targets_by: dict = {}
    cat_value_targets_by: dict = {}
    cat_name_map: dict = {}
    if date_from and date_to:
        months = _months_in_range(date_from, date_to)
        month_cond = or_(*[and_(ExecutiveTarget.year == y, ExecutiveTarget.month == m) for (y, m) in months])
        tfilters = [ExecutiveTarget.user_id.in_(ids), ExecutiveTarget.is_deleted == False, month_cond]  # noqa
        if tenant_id:
            tfilters.append(ExecutiveTarget.tenant_id == tenant_id)

        target_rows = (await db.execute(
            select(
                ExecutiveTarget.user_id, ExecutiveTarget.target_type,
                func.coalesce(func.sum(ExecutiveTarget.target_value), 0),
            ).where(*tfilters, ExecutiveTarget.category_id.is_(None))
            .group_by(ExecutiveTarget.user_id, ExecutiveTarget.target_type)
        )).all()
        for uid, ttype, tval in target_rows:
            targets_by.setdefault(uid, {})[ttype] = float(tval)

        cat_target_rows = (await db.execute(
            select(
                ExecutiveTarget.user_id, ExecutiveTarget.category_id, ExecutiveTarget.target_type,
                func.coalesce(func.sum(ExecutiveTarget.target_value), 0),
            ).where(
                *tfilters,
                ExecutiveTarget.target_type.in_([TargetType.category_quantity, TargetType.category_value]),
                ExecutiveTarget.category_id.isnot(None),
            ).group_by(ExecutiveTarget.user_id, ExecutiveTarget.category_id, ExecutiveTarget.target_type)
        )).all()
        for uid, cid, ttype, tval in cat_target_rows:
            if ttype == TargetType.category_quantity:
                cat_piece_targets_by.setdefault(uid, {})[str(cid)] = float(tval)
            else:
                cat_value_targets_by.setdefault(uid, {})[str(cid)] = float(tval)

        target_cids = {
            cid for maps in (cat_piece_targets_by, cat_value_targets_by)
            for m in maps.values() for cid in m
        }
        if target_cids:
            name_rows = (await db.execute(
                select(Category.id, Category.name).where(Category.id.in_([uuid.UUID(c) for c in target_cids]))
            )).all()
            cat_name_map = {str(cid): name for cid, name in name_rows}

    def _exec_categories(exec_id):
        cats = [dict(c) for c in cat_by.get(exec_id, [])]
        pt = cat_piece_targets_by.get(exec_id, {})
        vt = cat_value_targets_by.get(exec_id, {})
        present = {c["categoryId"] for c in cats}
        for cid in set(pt) | set(vt):  # categories with a target but no sales → show as 0
            if cid not in present:
                cats.append({"categoryId": cid, "category": cat_name_map.get(cid, ""),
                             "pieces": 0, "value": 0})
                present.add(cid)
        for c in cats:
            tp, tv = pt.get(c["categoryId"]), vt.get(c["categoryId"])
            c["targetPieces"] = tp
            c["pieceAchievement"] = round(c["pieces"] / tp * 100, 2) if tp else None
            c["targetValue"] = tv
            c["valueAchievement"] = round(c["value"] / tv * 100, 2) if tv else None
        cats.sort(key=lambda c: c["value"], reverse=True)
        return cats

    result = []
    for e in execs:
        orders_n, value, delivered = orders_by.get(e.id, (0, 0.0, 0))
        days, dist, minutes, shops = att_by.get(e.id, (0, 0.0, 0, 0))
        pieces_n = pieces_by.get(e.id, 0)
        tmap = targets_by.get(e.id, {})
        count_target = tmap.get(TargetType.order_count, 0)
        value_target = tmap.get(TargetType.order_value, 0)
        pieces_target = tmap.get(TargetType.order_pieces, 0)
        result.append({
            "userId": str(e.id),
            "name": f"{e.first_name} {e.last_name or ''}".strip(),
            "phone": e.phone,
            "districts": ", ".join(ud.district.name for ud in e.user_districts if ud.district),
            "orders": orders_n,
            "orderValue": round(value, 2),
            "pieces": pieces_n,
            "delivered": delivered,
            "deliveryRate": round(delivered / orders_n * 100, 2) if orders_n else 0,
            "orderCountTarget": count_target,
            "countAchievement": round(orders_n / count_target * 100, 2) if count_target else None,
            "orderValueTarget": value_target,
            "valueAchievement": round(value / value_target * 100, 2) if value_target else None,
            "orderPiecesTarget": pieces_target,
            "piecesAchievement": round(pieces_n / pieces_target * 100, 2) if pieces_target else None,
            "daysWorked": days,
            "distanceKm": round(dist, 2),
            "workHours": round(minutes / 60, 2),
            "shopsVisited": shops,
            "byCategory": _exec_categories(e.id),
        })
    result.sort(key=lambda r: r["orderValue"], reverse=True)
    return result


async def get_distributor_kpis(db: AsyncSession, date_from, date_to, tenant_id=None) -> list[dict]:
    """Per-distributor KPIs — orders handled, delivered, value, pieces for the range."""
    dist_q = (
        select(User).join(User.role)
        .where(User.is_deleted == False, User.is_active == True, Role.name == "distributor")  # noqa
    )
    dists = (await db.execute(dist_q)).scalars().unique().all()
    if not dists:
        return []
    ids = [d.id for d in dists]

    ofilters = [
        Order.is_deleted == False, Order.distributor_id.in_(ids),  # noqa
        Order.parent_order_id == None, *_created_between(date_from, date_to),  # noqa
    ]
    if tenant_id:
        ofilters.append(Order.tenant_id == tenant_id)

    rows = (await db.execute(
        select(
            Order.distributor_id, func.count(Order.id),
            func.coalesce(func.sum(Order.total_amount), 0),
            func.coalesce(func.sum(case((Order.status == OrderStatus.delivered, 1), else_=0)), 0),
        ).where(*ofilters).group_by(Order.distributor_id)
    )).all()
    by = {r[0]: (int(r[1]), float(r[2]), int(r[3])) for r in rows}

    piece_rows = (await db.execute(
        select(Order.distributor_id, func.coalesce(func.sum(OrderItem.count), 0))
        .select_from(OrderItem).join(Order, OrderItem.order_id == Order.id)
        .where(*ofilters).group_by(Order.distributor_id)
    )).all()
    pieces_by = {r[0]: int(r[1]) for r in piece_rows}
    cat_by = await _category_breakdown(db, Order.distributor_id, ofilters)

    result = []
    for d in dists:
        handled, value, delivered = by.get(d.id, (0, 0.0, 0))
        result.append({
            "userId": str(d.id),
            "name": f"{d.first_name} {d.last_name or ''}".strip(),
            "phone": d.phone,
            "ordersHandled": handled,
            "value": round(value, 2),
            "pieces": pieces_by.get(d.id, 0),
            "delivered": delivered,
            "deliveryRate": round(delivered / handled * 100, 2) if handled else 0,
            "byCategory": cat_by.get(d.id, []),
        })
    result.sort(key=lambda r: r["value"], reverse=True)
    return result


async def get_shop_kpis(
    db: AsyncSession, date_from, date_to, district_id=None, tenant_id=None, limit: int = 100,
) -> list[dict]:
    """Per-shop KPIs — orders, value, pieces and last order date for the range."""
    ofilters = [Order.is_deleted == False, *_created_between(date_from, date_to)]  # noqa
    if tenant_id:
        ofilters.append(Order.tenant_id == tenant_id)

    order_rows = (await db.execute(
        select(
            Order.shop_id, func.count(Order.id),
            func.coalesce(func.sum(Order.total_amount), 0),
            func.max(Order.created_at),
        ).where(*ofilters).group_by(Order.shop_id)
    )).all()
    agg = {r[0]: (int(r[1]), float(r[2]), r[3]) for r in order_rows}

    piece_rows = (await db.execute(
        select(Order.shop_id, func.coalesce(func.sum(OrderItem.count), 0))
        .select_from(OrderItem).join(Order, OrderItem.order_id == Order.id)
        .where(*ofilters).group_by(Order.shop_id)
    )).all()
    pieces_by = {r[0]: int(r[1]) for r in piece_rows}
    cat_by = await _category_breakdown(db, Order.shop_id, ofilters)

    shop_q = (
        select(Shop).where(Shop.is_deleted == False)  # noqa
        .options(selectinload(Shop.district), selectinload(Shop.taluk))
    )
    if district_id:
        shop_q = shop_q.where(Shop.district_id == district_id)
    shops = (await db.execute(shop_q)).scalars().unique().all()

    result = []
    for s in shops:
        orders_n, value, last = agg.get(s.id, (0, 0.0, None))
        result.append({
            "shopId": str(s.id),
            "name": s.name,
            "district": s.district.name if s.district else None,
            "taluk": s.taluk.name if s.taluk else None,
            "isActive": s.is_active,
            "isEbo": s.is_ebo,
            "orders": orders_n,
            "value": round(value, 2),
            "pieces": pieces_by.get(s.id, 0),
            "byCategory": cat_by.get(s.id, []),
            "lastOrderDate": last.isoformat() if last else None,
        })
    result.sort(key=lambda r: r["value"], reverse=True)
    return result[:limit]


async def get_executive_route(db: AsyncSession, user_id: uuid.UUID, work_date: date) -> dict:
    """An executive's travelled route for one day, map-ready.

    - `route`   : ordered GPS points (check-in → pings → check-out) for the map polyline.
    - `shopVisits`: shop markers with entry/exit time and dwell duration.
    - `checkin` / `checkout`: start / end markers.
    - `summary` : distance, hours, shops for the day.
    Times are ISO with UTC offset — localise on the client.
    """
    user = await db.scalar(select(User).where(User.id == user_id))
    name = f"{user.first_name} {user.last_name or ''}".strip() if user else ""

    log = (await db.execute(
        select(WorkLog)
        .where(
            WorkLog.user_id == user_id,
            WorkLog.work_date == work_date,
            WorkLog.is_deleted == False,  # noqa
        )
        .options(
            selectinload(WorkLog.location_events),
            selectinload(WorkLog.shop_visits).selectinload(ShopVisit.shop),
        )
    )).scalar_one_or_none()

    base = {"userId": str(user_id), "name": name, "date": str(work_date)}
    if not log:
        return {
            **base, "checkin": None, "checkout": None, "route": [], "shopVisits": [],
            "summary": {"distanceKm": 0, "workHours": 0, "shopsVisited": 0, "pointCount": 0},
        }

    route_types = (
        LocationEventType.location_ping,
        LocationEventType.checkin,
        LocationEventType.checkout,
    )
    route = [
        {
            "lat": float(e.latitude),
            "lng": float(e.longitude),
            "at": e.recorded_at.isoformat() if e.recorded_at else None,
            "type": e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type),
        }
        for e in sorted(
            (e for e in log.location_events if e.event_type in route_types),
            key=lambda x: x.recorded_at,
        )
    ]

    shop_visits = [
        {
            "shopId": str(v.shop_id),
            "shopName": v.shop.name if v.shop else None,
            "lat": float(v.entry_lat) if v.entry_lat is not None else None,
            "lng": float(v.entry_lng) if v.entry_lng is not None else None,
            "entryAt": v.entry_at.isoformat() if v.entry_at else None,
            "exitAt": v.exit_at.isoformat() if v.exit_at else None,
            "durationMinutes": v.duration_minutes,
        }
        for v in sorted(log.shop_visits, key=lambda x: x.entry_at)
    ]

    def _point(at, lat, lng, address=None):
        if at is None or lat is None or lng is None:
            return None
        p = {"lat": float(lat), "lng": float(lng), "at": at.isoformat()}
        if address is not None:
            p["address"] = address
        return p

    return {
        **base,
        "checkin": _point(log.checkin_at, log.checkin_lat, log.checkin_lng, log.checkin_address),
        "checkout": _point(log.checkout_at, log.checkout_lat, log.checkout_lng, log.checkout_address),
        "route": route,
        "shopVisits": shop_visits,
        "summary": {
            "distanceKm": float(log.total_distance_km) if log.total_distance_km is not None else 0,
            "workHours": round(log.total_work_minutes / 60, 2) if log.total_work_minutes else 0,
            "shopsVisited": log.total_shops_visited or 0,
            "pointCount": len(route),
        },
    }
