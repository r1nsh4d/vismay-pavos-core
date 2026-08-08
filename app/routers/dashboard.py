import uuid
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_roles
from app.schemas.common import CommonResponse, ResponseModel
from app.models.order import OrderStatus
from app.services import dashboard as dash_svc

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
