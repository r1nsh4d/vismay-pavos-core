import uuid
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.common import CommonResponse, ResponseModel, ErrorResponseModel
from app.schemas.target import TargetCreate, TargetResponse
from app.services import targets as target_svc
from app.models.user import User
from app.models.order import OrderStatus

router = APIRouter(prefix="/targets", tags=["Targets"])


def _parse_statuses(status: str | None) -> list[OrderStatus] | None:
    """Parse a comma-separated `status` query param into OrderStatus values, ignoring
    blanks and unknown values. Returns None when nothing usable was given."""
    if not status:
        return None
    out: list[OrderStatus] = []
    for part in status.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(OrderStatus(part))
        except ValueError:
            continue
    return out or None


@router.post("", response_model=CommonResponse)
async def set_target(
    target_in: TargetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Admin sets target for an executive.

    Examples:
    - order_count: { targetType: "order_count", targetValue: 50 }
    - order_value: { targetType: "order_value", targetValue: 500000 }
    - category_quantity: { targetType: "category_quantity", categoryId: "uuid", targetValue: 1000 }
    """
    target = await target_svc.set_target(db, target_in)
    await db.commit()
    return ResponseModel(
        data=target_svc.serialize_target(target),
        message="Target set successfully",
    )


@router.get("/all-executives", response_model=CommonResponse)
async def get_all_executives_summary(
    year: int | None = None,
    month: int | None = None,
    tenant_id: uuid.UUID | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin view — all executives and their achievement this month. Pass `status` (one or
    comma-separated) to count only orders in those statuses."""
    now = datetime.utcnow()
    summaries = await target_svc.get_all_executives_summary(
        db,
        year=year or now.year,
        month=month or now.month,
        tenant_id=tenant_id,
        statuses=_parse_statuses(status),
    )
    return ResponseModel(data=summaries, message="All executives summary fetched")


@router.get("/my/achievement", response_model=CommonResponse)
async def get_my_achievement(
    year: int | None = None,
    month: int | None = None,
    tenant_id: uuid.UUID | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Executive checks their own achievement. Pass `tenant_id` to scope to one tenant
    (targets are per tenant); omit it to aggregate across all the executive's tenants.
    Pass `status` (one value or comma-separated, e.g. `delivered` or `billed,delivered`)
    to count only orders in those statuses; omit it to count all except
    rejected/returned/cancelled.

    NOTE: this literal route MUST stay above the `/{user_id}` routes — otherwise
    Starlette matches `/{user_id}` first and tries to parse "my" as a UUID (→ 422).
    """
    now = datetime.utcnow()
    summary = await target_svc.get_achievement_summary(
        db,
        user_id=current_user.id,
        year=year or now.year,
        month=month or now.month,
        tenant_id=tenant_id,
        statuses=_parse_statuses(status),
    )
    return ResponseModel(data=summary, message="My achievement fetched")


@router.get("/{user_id}", response_model=CommonResponse)
async def get_targets(
    user_id: uuid.UUID,
    year: int | None = None,
    month: int | None = None,
    tenant_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get targets set for an executive for a month. Pass `tenant_id` to list only that
    tenant's targets (so the Manage panel matches the tenant-scoped achievement columns)."""
    now = datetime.utcnow()
    targets = await target_svc.get_targets_by_user(
        db,
        user_id=user_id,
        year=year or now.year,
        month=month or now.month,
        tenant_id=tenant_id,
    )
    return ResponseModel(
        data=[target_svc.serialize_target(t) for t in targets],
        message="Targets fetched",
    )


@router.get("/{user_id}/achievement", response_model=CommonResponse)
async def get_achievement(
    user_id: uuid.UUID,
    year: int | None = None,
    month: int | None = None,
    tenant_id: uuid.UUID | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get achievement vs targets for an executive. Pass `tenant_id` to scope to one tenant,
    and `status` (one or comma-separated) to count only orders in those statuses."""
    now = datetime.utcnow()
    summary = await target_svc.get_achievement_summary(
        db,
        user_id=user_id,
        year=year or now.year,
        month=month or now.month,
        tenant_id=tenant_id,
        statuses=_parse_statuses(status),
    )
    return ResponseModel(data=summary, message="Achievement fetched")


@router.delete("/{user_id}/{target_id}", response_model=CommonResponse)
async def delete_target(
    user_id: uuid.UUID,
    target_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = await target_svc.delete_target(db, user_id=user_id, target_id=target_id)
    if not deleted:
        return ErrorResponseModel(code=404, message="Target not found", error={})
    await db.commit()
    return ResponseModel(data=None, message="Target deleted")