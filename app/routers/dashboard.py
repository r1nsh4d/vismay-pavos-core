import uuid
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_roles
from app.schemas.common import CommonResponse, ResponseModel
from app.models.order import OrderStatus
from app.services import dashboard as dash_svc
from app.services.report_export import generate_excel
from app.routers.reports import excel_response, _now_str

# Admin dashboard — read-only. Restricted to management roles.
router = APIRouter(
    prefix="/dashboard", tags=["Dashboard"],
    dependencies=[Depends(require_roles("super_admin", "admin", "scm_user"))],
)


def _default_range(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    """Default an unset date range to today, so the dashboard shows current-day data."""
    today = datetime.now(timezone.utc).date()
    return (date_from or today, date_to or today)


@router.get("/orders/summary", response_model=CommonResponse)
async def order_summary(
    date_from: date | None = None,
    date_to: date | None = None,
    status: OrderStatus | None = None,
    tenant_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Per-day order counts / value / pieces with status + date filters.

    Defaults to **today** when no dates are given. Single day: date_from == date_to; any range works.
    """
    date_from, date_to = _default_range(date_from, date_to)
    data = await dash_svc.get_order_dashboard(
        db, date_from=date_from, date_to=date_to, status=status, tenant_id=tenant_id
    )
    return ResponseModel(data=data, message="Order dashboard fetched")


@router.get("/map/shops", response_model=CommonResponse)
async def map_shops(
    district_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Shops with coordinates for the map. Frontend renders the markers."""
    data = await dash_svc.get_map_shops(db, district_id=district_id, is_active=is_active)
    return ResponseModel(data=data, message="Shop map data fetched")


@router.get("/executives/status", response_model=CommonResponse)
async def executive_status(
    user_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Live status + latest location of executives today (for map markers + status list).

    Pass user_id to get a single executive; omit for all.
    """
    data = await dash_svc.get_executive_status_list(db, user_id=user_id)
    return ResponseModel(data=data, message="Executive status fetched")


@router.get("/attendance/summary", response_model=CommonResponse)
async def attendance_summary(
    db: AsyncSession = Depends(get_db),
):
    """Today's attendance roll-up: how many executives are logged in + the clickable agent list.

    `data.counts` for the header (activeNow / checkedOut / notCheckedIn …); `data.executives[]`
    is the list — click one and fetch GET /attendance/activity/{userId} for that agent's activity.
    """
    data = await dash_svc.get_attendance_overview(db)
    return ResponseModel(data=data, message="Attendance summary fetched")


# ── BI / Analytics tab (read-only; date range defaults to today) ─────────────────

@router.get("/top-products", response_model=CommonResponse)
async def top_products(
    date_from: date | None = None,
    date_to: date | None = None,
    tenant_id: uuid.UUID | None = None,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """Top products by order value (with pieces) for the range."""
    date_from, date_to = _default_range(date_from, date_to)
    data = await dash_svc.get_top_products(db, date_from, date_to, tenant_id, limit)
    return ResponseModel(data=data, message="Top products fetched")


@router.get("/executive-performance", response_model=CommonResponse)
async def executive_performance(
    date_from: date | None = None,
    date_to: date | None = None,
    tenant_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Per-executive orders / value / delivered / pieces for the range."""
    date_from, date_to = _default_range(date_from, date_to)
    data = await dash_svc.get_executive_performance(db, date_from, date_to, tenant_id)
    return ResponseModel(data=data, message="Executive performance fetched")


@router.get("/breakdown", response_model=CommonResponse)
async def breakdown(
    by: str = Query(..., description="Group by: district | shop | tenant | category"),
    date_from: date | None = None,
    date_to: date | None = None,
    tenant_id: uuid.UUID | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Sales grouped by district / shop / tenant / category for the range."""
    date_from, date_to = _default_range(date_from, date_to)
    data = await dash_svc.get_breakdown(db, by, date_from, date_to, tenant_id, limit)
    return ResponseModel(data=data, message=f"Breakdown by {by} fetched")


@router.get("/trend", response_model=CommonResponse)
async def trend(
    group: str = Query("day", description="Bucket by: day | week | month"),
    date_from: date | None = None,
    date_to: date | None = None,
    tenant_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Order count + value over time, bucketed by day/week/month."""
    date_from, date_to = _default_range(date_from, date_to)
    data = await dash_svc.get_trend(db, group, date_from, date_to, tenant_id)
    return ResponseModel(data=data, message="Trend fetched")


@router.get("/compare", response_model=CommonResponse)
async def compare(
    date_from: date | None = None,
    date_to: date | None = None,
    tenant_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Current range vs the preceding range of equal length, with % change."""
    date_from, date_to = _default_range(date_from, date_to)
    data = await dash_svc.get_period_comparison(db, date_from, date_to, tenant_id)
    return ResponseModel(data=data, message="Period comparison fetched")


# ── KPI monitoring tab (entity-level metrics; date range defaults to today) ──────

@router.get("/kpi/overview", response_model=CommonResponse)
async def kpi_overview(
    date_from: date | None = None,
    date_to: date | None = None,
    tenant_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Headline counts for every entity + order/attendance metrics — the KPI tab's top cards."""
    date_from, date_to = _default_range(date_from, date_to)
    data = await dash_svc.get_kpi_overview(db, date_from, date_to, tenant_id)
    return ResponseModel(data=data, message="KPI overview fetched")


@router.get("/kpi/executives", response_model=CommonResponse)
async def kpi_executives(
    date_from: date | None = None,
    date_to: date | None = None,
    tenant_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Per-executive KPIs — orders, value, delivery, plus attendance (days, distance, shops)."""
    date_from, date_to = _default_range(date_from, date_to)
    data = await dash_svc.get_executive_kpis(db, date_from, date_to, tenant_id)
    return ResponseModel(data=data, message="Executive KPIs fetched")


@router.get("/kpi/distributors", response_model=CommonResponse)
async def kpi_distributors(
    date_from: date | None = None,
    date_to: date | None = None,
    tenant_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Per-distributor KPIs — orders handled, delivered, value, pieces for the range."""
    date_from, date_to = _default_range(date_from, date_to)
    data = await dash_svc.get_distributor_kpis(db, date_from, date_to, tenant_id)
    return ResponseModel(data=data, message="Distributor KPIs fetched")


@router.get("/kpi/shops", response_model=CommonResponse)
async def kpi_shops(
    date_from: date | None = None,
    date_to: date | None = None,
    district_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Per-shop KPIs — orders, value, pieces and last order date for the range."""
    date_from, date_to = _default_range(date_from, date_to)
    data = await dash_svc.get_shop_kpis(db, date_from, date_to, district_id, tenant_id, limit)
    return ResponseModel(data=data, message="Shop KPIs fetched")


@router.get("/executives/{user_id}/route", response_model=CommonResponse)
async def executive_route(
    user_id: uuid.UUID,
    date: date | None = None,
    db: AsyncSession = Depends(get_db),
):
    """An executive's travelled route for a day — map-ready polyline + shop/check-in markers.

    Defaults to today. Draw `route` as a polyline; place markers from `checkin`, `checkout`
    and `shopVisits`.
    """
    day = date or datetime.now(timezone.utc).date()
    data = await dash_svc.get_executive_route(db, user_id, day)
    return ResponseModel(data=data, message="Executive route fetched")


# ── KPI table Excel exports (the same rows as the JSON KPI endpoints, flattened) ──

@router.get("/kpi/executives/excel")
async def kpi_executives_excel(
    date_from: date | None = None,
    date_to: date | None = None,
    tenant_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Executive KPI table as Excel (per-category detail is omitted from the flat sheet)."""
    date_from, date_to = _default_range(date_from, date_to)
    rows = await dash_svc.get_executive_kpis(db, date_from, date_to, tenant_id)
    flat = [{
        "Executive": r["name"], "Phone": r["phone"], "Districts": r["districts"],
        "Orders": r["orders"], "Order Value": r["orderValue"], "Pieces": r["pieces"],
        "Delivered": r["delivered"], "Delivery Rate %": r["deliveryRate"],
        "Count Target": r["orderCountTarget"], "Count Achv %": r["countAchievement"],
        "Value Target": r["orderValueTarget"], "Value Achv %": r["valueAchievement"],
        "Pieces Target": r["orderPiecesTarget"], "Pieces Achv %": r["piecesAchievement"],
        "Days Worked": r["daysWorked"], "Distance (km)": r["distanceKm"],
        "Work Hours": r["workHours"], "Shops Visited": r["shopsVisited"],
    } for r in rows]
    return excel_response(generate_excel(flat, "Executive KPIs"), f"executive_kpis_{_now_str()}")


@router.get("/kpi/distributors/excel")
async def kpi_distributors_excel(
    date_from: date | None = None,
    date_to: date | None = None,
    tenant_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Distributor KPI table as Excel."""
    date_from, date_to = _default_range(date_from, date_to)
    rows = await dash_svc.get_distributor_kpis(db, date_from, date_to, tenant_id)
    flat = [{
        "Distributor": r["name"], "Phone": r["phone"],
        "Orders Handled": r["ordersHandled"], "Value": r["value"], "Pieces": r["pieces"],
        "Delivered": r["delivered"], "Delivery Rate %": r["deliveryRate"],
    } for r in rows]
    return excel_response(generate_excel(flat, "Distributor KPIs"), f"distributor_kpis_{_now_str()}")


@router.get("/kpi/shops/excel")
async def kpi_shops_excel(
    date_from: date | None = None,
    date_to: date | None = None,
    district_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    limit: int = 1000,
    db: AsyncSession = Depends(get_db),
):
    """Shop KPI table as Excel."""
    date_from, date_to = _default_range(date_from, date_to)
    rows = await dash_svc.get_shop_kpis(db, date_from, date_to, district_id, tenant_id, limit)
    flat = [{
        "Shop": r["name"], "District": r["district"], "Taluk": r["taluk"],
        "Status": "Active" if r["isActive"] else "Inactive",
        "EBO": "Yes" if r["isEbo"] else "No",
        "Orders": r["orders"], "Value": r["value"], "Pieces": r["pieces"],
        "Last Order": (r["lastOrderDate"][:10] if r["lastOrderDate"] else ""),
    } for r in rows]
    return excel_response(generate_excel(flat, "Shop KPIs"), f"shop_kpis_{_now_str()}")
