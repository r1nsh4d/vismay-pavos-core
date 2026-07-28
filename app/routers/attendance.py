import uuid
from datetime import date, datetime
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.common import CommonResponse, ResponseModel, ErrorResponseModel, PaginatedResponse
from app.schemas.attendance import (
    CheckInInput, CheckOutInput, LocationPingInput,
    ShopEntryInput, ShopExitInput,
)
from app.services import attendance as att_svc
from app.models.user import User

router = APIRouter(prefix="/attendance", tags=["Attendance"])


# ── Check In / Out ─────────────────────────────────────────────────────────────

@router.post("/checkin", response_model=CommonResponse)
async def check_in(
    data: CheckInInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Executive checks in at start of work day."""
    work_log = await att_svc.check_in(
        db,
        user_id=current_user.id,
        latitude=data.latitude,
        longitude=data.longitude,
        accuracy=data.accuracy,
        address=data.address,
    )
    await db.commit()
    return ResponseModel(
        data=att_svc.serialize_work_log(work_log),
        message="Checked in successfully"
    )


@router.post("/checkout", response_model=CommonResponse)
async def check_out(
    data: CheckOutInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Executive checks out at end of work day."""
    work_log = await att_svc.check_out(
        db,
        user_id=current_user.id,
        latitude=data.latitude,
        longitude=data.longitude,
        accuracy=data.accuracy,
        address=data.address,
        notes=data.notes,
    )
    await db.commit()
    return ResponseModel(
        data=att_svc.serialize_work_log(work_log),
        message="Checked out successfully"
    )


# ── Location Ping ──────────────────────────────────────────────────────────────

@router.post("/ping", response_model=CommonResponse)
async def location_ping(
    data: LocationPingInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send GPS location ping every 5 minutes while working.
    Used to track travel route and calculate total distance.
    """
    event = await att_svc.record_location_ping(
        db,
        user_id=current_user.id,
        latitude=data.latitude,
        longitude=data.longitude,
        accuracy=data.accuracy,
        recorded_at=data.recorded_at,
    )
    await db.commit()
    return ResponseModel(
        data={
            "id": str(event.id),
            "recordedAt": event.recorded_at.isoformat(),
            "latitude": float(event.latitude),
            "longitude": float(event.longitude),
        },
        message="Location recorded"
    )


# ── Shop Entry / Exit ──────────────────────────────────────────────────────────

@router.post("/shop-entry", response_model=CommonResponse)
async def shop_entry(
    data: ShopEntryInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Log entry into a shop."""
    visit = await att_svc.record_shop_entry(
        db,
        user_id=current_user.id,
        shop_id=data.shop_id,
        latitude=data.latitude,
        longitude=data.longitude,
        accuracy=data.accuracy,
    )
    await db.commit()
    return ResponseModel(
        data={
            "visitId": str(visit.id),
            "shopId": str(visit.shop_id),
            "entryAt": visit.entry_at.isoformat(),
        },
        message="Shop entry recorded"
    )


@router.post("/shop-exit", response_model=CommonResponse)
async def shop_exit(
    data: ShopExitInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Log exit from a shop."""
    visit = await att_svc.record_shop_exit(
        db,
        user_id=current_user.id,
        shop_id=data.shop_id,
        latitude=data.latitude,
        longitude=data.longitude,
        accuracy=data.accuracy,
        notes=data.notes,
    )
    await db.commit()
    return ResponseModel(
        data={
            "visitId": str(visit.id),
            "shopId": str(visit.shop_id),
            "entryAt": visit.entry_at.isoformat(),
            "exitAt": visit.exit_at.isoformat() if visit.exit_at else None,
            "durationMinutes": visit.duration_minutes,
        },
        message="Shop exit recorded"
    )


# ── Today's status ─────────────────────────────────────────────────────────────

@router.get("/today", response_model=CommonResponse)
async def get_today(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get today's work log with full detail — for executive's app."""
    work_log = await att_svc.get_today_work_log(db, user_id=current_user.id)
    if not work_log:
        return ResponseModel(
            data={
                "isCheckedIn": False,
                "isCheckedOut": False,
                "workDate": str(datetime.now(tz=None).date()),
            },
            message="No check-in yet today"
        )
    return ResponseModel(
        data=att_svc.serialize_work_log_detail(work_log),
        message="Today's work log fetched"
    )


# ── Work Log History ───────────────────────────────────────────────────────────

@router.get("/my/logs", response_model=CommonResponse)
async def get_my_logs(
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Executive's own work log history."""
    logs, total = await att_svc.get_work_logs(
        db,
        user_id=current_user.id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        limit=limit,
    )
    return PaginatedResponse(
        data=[att_svc.serialize_work_log(l) for l in logs],
        message="Work logs fetched",
        page=page,
        limit=limit,
        total=total,
    )


@router.get("/my/logs/{work_date}", response_model=CommonResponse)
async def get_my_log_by_date(
    work_date: date,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get full detail of a specific day — includes route points and shop visits."""
    log = await att_svc.get_work_log_by_date(db, user_id=current_user.id, work_date=work_date)
    if not log:
        return ErrorResponseModel(code=404, message="No work log found for this date", error={})
    return ResponseModel(
        data=att_svc.serialize_work_log_detail(log),
        message="Work log fetched"
    )


@router.get("/my/travel-allowance", response_model=CommonResponse)
async def get_my_travel_allowance(
    year: int | None = None,
    month: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Executive's own travel allowance summary for a month."""
    now = datetime.utcnow()
    summary = await att_svc.get_travel_allowance_summary(
        db,
        user_id=current_user.id,
        year=year or now.year,
        month=month or now.month,
    )
    return ResponseModel(data=summary, message="Travel allowance summary fetched")


@router.get("/my/activity", response_model=CommonResponse)
async def get_my_activity(
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Own activity over a date range — totals + per-day breakdown with shop visits.

    Defaults to the current month; pass the same date for date_from and date_to
    to get a single day.
    """
    today = datetime.now(tz=None).date()
    summary = await att_svc.get_activity_summary(
        db,
        user_id=current_user.id,
        date_from=date_from or today.replace(day=1),
        date_to=date_to or today,
    )
    return ResponseModel(data=summary, message="Activity summary fetched")


# ── Admin / Manager views ──────────────────────────────────────────────────────

@router.get("/logs", response_model=CommonResponse)
async def get_all_logs(
    user_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin view — all executives work logs."""
    logs, total = await att_svc.get_work_logs(
        db,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        limit=limit,
    )
    return PaginatedResponse(
        data=[att_svc.serialize_work_log(l) for l in logs],
        message="Work logs fetched",
        page=page,
        limit=limit,
        total=total,
    )


@router.get("/logs/{user_id}/{work_date}", response_model=CommonResponse)
async def get_log_by_user_date(
    user_id: uuid.UUID,
    work_date: date,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin view — full work log detail for a specific executive on a specific date."""
    log = await att_svc.get_work_log_by_date(db, user_id=user_id, work_date=work_date)
    if not log:
        return ErrorResponseModel(code=404, message="No work log found", error={})
    return ResponseModel(
        data=att_svc.serialize_work_log_detail(log),
        message="Work log fetched"
    )


@router.get("/travel-allowance/{user_id}", response_model=CommonResponse)
async def get_travel_allowance(
    user_id: uuid.UUID,
    year: int | None = None,
    month: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin view — travel allowance summary for a specific executive."""
    now = datetime.utcnow()
    summary = await att_svc.get_travel_allowance_summary(
        db,
        user_id=user_id,
        year=year or now.year,
        month=month or now.month,
    )
    return ResponseModel(data=summary, message="Travel allowance summary fetched")


@router.get("/activity/{user_id}", response_model=CommonResponse)
async def get_activity(
    user_id: uuid.UUID,
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin view — one executive's activity over a date range (single day to multiple)."""
    today = datetime.now(tz=None).date()
    summary = await att_svc.get_activity_summary(
        db,
        user_id=user_id,
        date_from=date_from or today.replace(day=1),
        date_to=date_to or today,
    )
    return ResponseModel(data=summary, message="Activity summary fetched")