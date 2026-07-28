import uuid
from datetime import date
from fastapi import APIRouter, Depends
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


@router.get("/orders/summary", response_model=CommonResponse)
async def order_summary(
    date_from: date | None = None,
    date_to: date | None = None,
    status: OrderStatus | None = None,
    tenant_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Per-day order counts / value / pieces with status + date filters.

    Single day: date_from == date_to. Month or custom span: any range. Omit both for all-time.
    """
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
