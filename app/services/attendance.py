import uuid
import math
from datetime import datetime, date, timezone, timedelta
from typing import Optional, List, Tuple
from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.attendance import WorkLog, LocationEvent, ShopVisit, LocationEventType, AttendanceStatus
from app.models.shop import Shop
from app.core.exceptions import AppException
from app.config import settings


def _now():
    return datetime.now(timezone.utc)


def _today():
    return datetime.now(timezone.utc).date()


def _aware(dt):
    """Normalise a datetime to timezone-aware UTC for safe comparison."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance between two GPS coordinates in km."""
    R = 6371.0
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def _get_or_create_work_log(
    db: AsyncSession,
    user_id: uuid.UUID,
    work_date: date,
) -> WorkLog:
    existing = await db.scalar(
        select(WorkLog).where(
            WorkLog.user_id == user_id,
            WorkLog.work_date == work_date,
            WorkLog.is_deleted == False,
        )
    )
    if existing:
        return existing

    work_log = WorkLog(
        user_id=user_id,
        work_date=work_date,
        status=AttendanceStatus.present,
        total_shops_visited=0,
    )
    db.add(work_log)
    await db.flush()
    return work_log


async def _calculate_total_distance(db: AsyncSession, work_log_id: uuid.UUID) -> float:
    """
    Total distance travelled in the day, cleaned for GPS noise.

    1. Order all location pings by time.
    2. Drop pings whose reported accuracy is worse than TA_GPS_MAX_ACCURACY_M.
    3. Sum straight-line (Haversine) hops, skipping:
         - hops shorter than TA_MIN_SEGMENT_M  (GPS drift while stationary), and
         - hops that fall entirely inside a shop visit (standstill drift).
    4. Multiply by TA_ROAD_FACTOR to approximate road distance vs crow-flies.
    """
    result = await db.execute(
        select(LocationEvent)
        .where(
            LocationEvent.work_log_id == work_log_id,
            LocationEvent.event_type == LocationEventType.location_ping,
        )
        .order_by(LocationEvent.recorded_at.asc())
    )
    pings = result.scalars().all()

    # Shop-visit time windows — used to ignore drift accumulated while inside a shop.
    intervals = []
    if settings.TA_EXCLUDE_IN_SHOP:
        visits = (await db.execute(
            select(ShopVisit).where(ShopVisit.work_log_id == work_log_id)
        )).scalars().all()
        intervals = [(_aware(v.entry_at), _aware(v.exit_at)) for v in visits if v.entry_at]

    def _inside_shop(ts) -> bool:
        ts = _aware(ts)
        for start, end in intervals:
            if start and ts >= start and (end is None or ts <= end):
                return True
        return False

    max_acc = settings.TA_GPS_MAX_ACCURACY_M
    kept = [p for p in pings if p.accuracy is None or float(p.accuracy) <= max_acc]
    # If the accuracy filter dropped almost everything (phones often report >50 m), it would
    # zero out the distance — fall back to the raw pings rather than reporting 0.
    if len(kept) < 2 and len(pings) >= 2:
        kept = list(pings)

    total_m = 0.0
    for i in range(1, len(kept)):
        a, b = kept[i - 1], kept[i]
        seg_m = _haversine_km(
            float(a.latitude), float(a.longitude),
            float(b.latitude), float(b.longitude),
        ) * 1000.0

        if seg_m < settings.TA_MIN_SEGMENT_M:
            continue  # jitter / standing still
        if _inside_shop(a.recorded_at) and _inside_shop(b.recorded_at):
            continue  # drift while parked inside a shop

        total_m += seg_m

    total_km = (total_m / 1000.0) * settings.TA_ROAD_FACTOR
    return round(total_km, 2)


# ── Check In ───────────────────────────────────────────────────────────────────

async def check_in(
    db: AsyncSession,
    user_id: uuid.UUID,
    latitude: float,
    longitude: float,
    accuracy: Optional[float] = None,
    address: Optional[str] = None,
) -> WorkLog:
    today = _today()

    # Check if already checked in today
    existing = await db.scalar(
        select(WorkLog).where(
            WorkLog.user_id == user_id,
            WorkLog.work_date == today,
            WorkLog.is_deleted == False,
        )
    )
    if existing and existing.checkin_at:
        raise AppException(status_code=400, detail="Already checked in today")

    work_log = await _get_or_create_work_log(db, user_id, today)
    now = _now()

    work_log.checkin_at = now
    work_log.checkin_lat = latitude
    work_log.checkin_lng = longitude
    work_log.checkin_address = address

    # Log the checkin event
    db.add(LocationEvent(
        work_log_id=work_log.id,
        user_id=user_id,
        event_type=LocationEventType.checkin,
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
        address=address,
        recorded_at=now,
    ))

    # Also add as first location ping for distance tracking
    db.add(LocationEvent(
        work_log_id=work_log.id,
        user_id=user_id,
        event_type=LocationEventType.location_ping,
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
        recorded_at=now,
    ))

    await db.flush()
    return work_log


# ── Check Out ──────────────────────────────────────────────────────────────────

async def check_out(
    db: AsyncSession,
    user_id: uuid.UUID,
    latitude: float,
    longitude: float,
    accuracy: Optional[float] = None,
    address: Optional[str] = None,
    notes: Optional[str] = None,
) -> WorkLog:
    today = _today()

    work_log = await db.scalar(
        select(WorkLog).where(
            WorkLog.user_id == user_id,
            WorkLog.work_date == today,
            WorkLog.is_deleted == False,
        )
    )
    if not work_log:
        raise AppException(status_code=400, detail="No check-in found for today")
    if not work_log.checkin_at:
        raise AppException(status_code=400, detail="Must check in before checking out")
    if work_log.checkout_at:
        raise AppException(status_code=400, detail="Already checked out today")

    now = _now()

    work_log.checkout_at = now
    work_log.checkout_lat = latitude
    work_log.checkout_lng = longitude
    work_log.checkout_address = address
    if notes:
        work_log.notes = notes

    # Calculate work duration
    checkin_time = work_log.checkin_at
    if checkin_time.tzinfo is None:
        checkin_time = checkin_time.replace(tzinfo=timezone.utc)
    work_log.total_work_minutes = int((now - checkin_time).total_seconds() / 60)

    # Calculate total distance from pings
    # Add final ping first
    db.add(LocationEvent(
        work_log_id=work_log.id,
        user_id=user_id,
        event_type=LocationEventType.location_ping,
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
        recorded_at=now,
    ))

    # Log the checkout event
    db.add(LocationEvent(
        work_log_id=work_log.id,
        user_id=user_id,
        event_type=LocationEventType.checkout,
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
        address=address,
        recorded_at=now,
    ))

    await db.flush()

    total_distance = await _calculate_total_distance(db, work_log.id)
    work_log.total_distance_km = total_distance

    # Close any open shop visits
    open_visits = (await db.execute(
        select(ShopVisit).where(
            ShopVisit.work_log_id == work_log.id,
            ShopVisit.exit_at.is_(None),
        )
    )).scalars().all()

    for visit in open_visits:
        visit.exit_at = now
        entry_time = visit.entry_at
        if entry_time.tzinfo is None:
            entry_time = entry_time.replace(tzinfo=timezone.utc)
        visit.duration_minutes = int((now - entry_time).total_seconds() / 60)

    # Count total shops
    shop_count = (await db.execute(
        select(func.count(ShopVisit.id)).where(
            ShopVisit.work_log_id == work_log.id,
        )
    )).scalar() or 0
    work_log.total_shops_visited = shop_count

    # Auto cutoff: if worked less than 4 hours mark as half day
    if work_log.total_work_minutes and work_log.total_work_minutes < 240:
        work_log.status = AttendanceStatus.half_day
        work_log.auto_cutoff_applied = True

    await db.flush()
    return work_log


# ── Location Ping ──────────────────────────────────────────────────────────────

async def record_location_ping(
    db: AsyncSession,
    user_id: uuid.UUID,
    latitude: float,
    longitude: float,
    accuracy: Optional[float] = None,
    recorded_at: Optional[datetime] = None,
) -> LocationEvent:
    today = _today()

    work_log = await db.scalar(
        select(WorkLog).where(
            WorkLog.user_id == user_id,
            WorkLog.work_date == today,
            WorkLog.is_deleted == False,
            WorkLog.checkin_at.isnot(None),
            WorkLog.checkout_at.is_(None),
        )
    )
    if not work_log:
        raise AppException(
            status_code=400,
            detail="No active work session found. Please check in first."
        )

    ping_time = recorded_at or _now()
    if ping_time.tzinfo is None:
        ping_time = ping_time.replace(tzinfo=timezone.utc)

    event = LocationEvent(
        work_log_id=work_log.id,
        user_id=user_id,
        event_type=LocationEventType.location_ping,
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
        recorded_at=ping_time,
    )
    db.add(event)
    await db.flush()
    return event


# ── Shop Entry ─────────────────────────────────────────────────────────────────

async def record_shop_entry(
    db: AsyncSession,
    user_id: uuid.UUID,
    shop_id: uuid.UUID,
    latitude: float,
    longitude: float,
    accuracy: Optional[float] = None,
) -> ShopVisit:
    today = _today()

    work_log = await db.scalar(
        select(WorkLog).where(
            WorkLog.user_id == user_id,
            WorkLog.work_date == today,
            WorkLog.is_deleted == False,
            WorkLog.checkin_at.isnot(None),
            WorkLog.checkout_at.is_(None),
        )
    )
    if not work_log:
        raise AppException(status_code=400, detail="No active work session. Please check in first.")

    # Check shop exists
    shop = await db.scalar(select(Shop).where(Shop.id == shop_id))
    if not shop:
        raise AppException(status_code=404, detail="Shop not found")

    # Check if already inside this shop
    open_visit = await db.scalar(
        select(ShopVisit).where(
            ShopVisit.work_log_id == work_log.id,
            ShopVisit.shop_id == shop_id,
            ShopVisit.exit_at.is_(None),
        )
    )
    if open_visit:
        raise AppException(status_code=400, detail="Already checked into this shop")

    # ── Geofence: match the executive's live position against the shop's coordinates ──
    # First-ever entry with no shop coordinates → capture the current position as the
    # shop location (fills missing data only, never overwrites). Once a shop has
    # coordinates, entries are validated to be within the allowed radius.
    addr = dict(shop.address or {})
    shop_lat, shop_lng = addr.get("latitude"), addr.get("longitude")

    if shop_lat is None or shop_lng is None:
        addr["latitude"] = latitude
        addr["longitude"] = longitude
        shop.address = addr  # reassign so SQLAlchemy tracks the JSON change
    elif settings.SHOP_ENTRY_GEOFENCE:
        distance_m = _haversine_km(float(shop_lat), float(shop_lng), latitude, longitude) * 1000.0
        allowed_m = settings.SHOP_ENTRY_MAX_DISTANCE_M + (accuracy or 0)
        if distance_m > allowed_m:
            raise AppException(
                status_code=400,
                detail=(
                    f"You appear to be {int(distance_m)} m from the shop. "
                    f"You must be within {int(settings.SHOP_ENTRY_MAX_DISTANCE_M)} m to check in."
                ),
            )

    now = _now()

    visit = ShopVisit(
        work_log_id=work_log.id,
        user_id=user_id,
        shop_id=shop_id,
        entry_at=now,
        entry_lat=latitude,
        entry_lng=longitude,
    )
    db.add(visit)

    # Log location event
    db.add(LocationEvent(
        work_log_id=work_log.id,
        user_id=user_id,
        event_type=LocationEventType.shop_entry,
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
        recorded_at=now,
        shop_id=shop_id,
    ))

    await db.flush()
    return visit


# ── Shop Exit ──────────────────────────────────────────────────────────────────

async def record_shop_exit(
    db: AsyncSession,
    user_id: uuid.UUID,
    shop_id: uuid.UUID,
    latitude: float,
    longitude: float,
    accuracy: Optional[float] = None,
    notes: Optional[str] = None,
) -> ShopVisit:
    today = _today()

    work_log = await db.scalar(
        select(WorkLog).where(
            WorkLog.user_id == user_id,
            WorkLog.work_date == today,
            WorkLog.is_deleted == False,
        )
    )
    if not work_log:
        raise AppException(status_code=400, detail="No work log found for today")

    visit = await db.scalar(
        select(ShopVisit).where(
            ShopVisit.work_log_id == work_log.id,
            ShopVisit.shop_id == shop_id,
            ShopVisit.exit_at.is_(None),
        )
    )
    if not visit:
        raise AppException(status_code=400, detail="No open shop entry found for this shop")

    now = _now()
    visit.exit_at = now
    visit.exit_lat = latitude
    visit.exit_lng = longitude
    if notes:
        visit.notes = notes

    entry_time = visit.entry_at
    if entry_time.tzinfo is None:
        entry_time = entry_time.replace(tzinfo=timezone.utc)
    visit.duration_minutes = int((now - entry_time).total_seconds() / 60)

    # Log location event
    db.add(LocationEvent(
        work_log_id=work_log.id,
        user_id=user_id,
        event_type=LocationEventType.shop_exit,
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
        recorded_at=now,
        shop_id=shop_id,
    ))

    await db.flush()
    return visit


# ── Fetch ──────────────────────────────────────────────────────────────────────

async def get_today_work_log(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> Optional[WorkLog]:
    result = await db.execute(
        select(WorkLog)
        .where(
            WorkLog.user_id == user_id,
            WorkLog.work_date == _today(),
            WorkLog.is_deleted == False,
        )
        .options(
            selectinload(WorkLog.location_events),
            selectinload(WorkLog.shop_visits).selectinload(ShopVisit.shop),
        )
    )
    return result.scalar_one_or_none()


async def get_work_log_by_date(
    db: AsyncSession,
    user_id: uuid.UUID,
    work_date: date,
) -> Optional[WorkLog]:
    result = await db.execute(
        select(WorkLog)
        .where(
            WorkLog.user_id == user_id,
            WorkLog.work_date == work_date,
            WorkLog.is_deleted == False,
        )
        .options(
            selectinload(WorkLog.location_events).selectinload(LocationEvent.shop),
            selectinload(WorkLog.shop_visits).selectinload(ShopVisit.shop),
        )
    )
    return result.scalar_one_or_none()


async def get_work_logs(
    db: AsyncSession,
    user_id: Optional[uuid.UUID] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    page: int = 1,
    limit: int = 30,
) -> Tuple[List[WorkLog], int]:
    query = select(WorkLog).where(WorkLog.is_deleted == False)

    if user_id:
        query = query.where(WorkLog.user_id == user_id)
    if date_from:
        query = query.where(WorkLog.work_date >= date_from)
    if date_to:
        query = query.where(WorkLog.work_date <= date_to)

    total = (await db.execute(
        select(func.count(WorkLog.id)).where(
            WorkLog.is_deleted == False,
            *(
                [WorkLog.user_id == user_id] if user_id else []
            ),
            *(
                [WorkLog.work_date >= date_from] if date_from else []
            ),
            *(
                [WorkLog.work_date <= date_to] if date_to else []
            ),
        )
    )).scalar() or 0

    result = await db.execute(
        query
        .options(
            selectinload(WorkLog.shop_visits).selectinload(ShopVisit.shop),
        )
        .order_by(WorkLog.work_date.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    return result.scalars().all(), total


async def get_travel_allowance_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
    year: int,
    month: int,
) -> dict:
    from app.models.user import User

    user = await db.scalar(select(User).where(User.id == user_id))

    result = await db.execute(
        select(WorkLog)
        .where(
            WorkLog.user_id == user_id,
            WorkLog.is_deleted == False,
            extract("year", WorkLog.work_date) == year,
            extract("month", WorkLog.work_date) == month,
            WorkLog.checkin_at.isnot(None),
        )
        .options(
            selectinload(WorkLog.shop_visits).selectinload(ShopVisit.shop),
        )
        .order_by(WorkLog.work_date.asc())
    )
    logs = result.scalars().all()

    total_days = len(logs)
    total_distance = sum(float(l.total_distance_km or 0) for l in logs)
    total_minutes = sum(l.total_work_minutes or 0 for l in logs)
    total_shops = sum(l.total_shops_visited or 0 for l in logs)

    daily_breakdown = []
    for log in logs:
        shops_visited = [
            {
                "shopName": v.shop.name if v.shop else "",
                "entryAt": v.entry_at.isoformat() if v.entry_at else None,
                "exitAt": v.exit_at.isoformat() if v.exit_at else None,
                "durationMinutes": v.duration_minutes,
            }
            for v in log.shop_visits
        ]

        daily_breakdown.append({
            "date": str(log.work_date),
            "checkinAt": log.checkin_at.isoformat() if log.checkin_at else None,
            "checkoutAt": log.checkout_at.isoformat() if log.checkout_at else None,
            "workMinutes": log.total_work_minutes,
            "distanceKm": float(log.total_distance_km or 0),
            "shopsVisited": log.total_shops_visited or 0,
            "status": log.status,
            "shopDetails": shops_visited,
        })

    return {
        "userId": str(user_id),
        "userName": f"{user.first_name} {user.last_name}".strip() if user else "",
        "year": year,
        "month": month,
        "totalDaysWorked": total_days,
        "totalDistanceKm": round(total_distance, 2),
        "totalWorkHours": round(total_minutes / 60, 2),
        "totalShopsVisited": total_shops,
        "dailyBreakdown": daily_breakdown,
    }


async def get_activity_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
    date_from: date,
    date_to: date,
) -> dict:
    """Activity for one executive over any date range (single day to multiple months).

    Returns totals plus a per-day breakdown with that day's shop visits — the data
    a UI needs to render an employee's activity for a chosen time frame.
    """
    from app.models.user import User

    user = await db.scalar(select(User).where(User.id == user_id))

    result = await db.execute(
        select(WorkLog)
        .where(
            WorkLog.user_id == user_id,
            WorkLog.is_deleted == False,
            WorkLog.work_date >= date_from,
            WorkLog.work_date <= date_to,
        )
        .options(selectinload(WorkLog.shop_visits).selectinload(ShopVisit.shop))
        .order_by(WorkLog.work_date.asc())
    )
    logs = result.scalars().all()

    total_days = len(logs)
    total_distance = sum(float(l.total_distance_km or 0) for l in logs)
    total_minutes = sum(l.total_work_minutes or 0 for l in logs)
    total_shops = sum(l.total_shops_visited or 0 for l in logs)

    daily_breakdown = []
    for log in logs:
        daily_breakdown.append({
            "date": str(log.work_date),
            "checkinAt": log.checkin_at.isoformat() if log.checkin_at else None,
            "checkoutAt": log.checkout_at.isoformat() if log.checkout_at else None,
            "checkinAddress": log.checkin_address,
            "checkoutAddress": log.checkout_address,
            "workMinutes": log.total_work_minutes,
            "workHours": round(log.total_work_minutes / 60, 2) if log.total_work_minutes else 0,
            "distanceKm": float(log.total_distance_km or 0),
            "shopsVisited": log.total_shops_visited or 0,
            "status": log.status,
            "shopVisits": [
                {
                    "shopName": v.shop.name if v.shop else "",
                    "entryAt": v.entry_at.isoformat() if v.entry_at else None,
                    "exitAt": v.exit_at.isoformat() if v.exit_at else None,
                    "durationMinutes": v.duration_minutes,
                }
                for v in sorted(log.shop_visits, key=lambda x: x.entry_at)
            ],
        })

    return {
        "userId": str(user_id),
        "userName": f"{user.first_name} {user.last_name or ''}".strip() if user else "",
        "dateFrom": str(date_from),
        "dateTo": str(date_to),
        "totalDaysWorked": total_days,
        "totalDistanceKm": round(total_distance, 2),
        "totalWorkHours": round(total_minutes / 60, 2),
        "totalShopsVisited": total_shops,
        "dailyBreakdown": daily_breakdown,
    }


# ── Serialization ──────────────────────────────────────────────────────────────

def serialize_work_log(log: WorkLog) -> dict:
    return {
        "id": str(log.id),
        "userId": str(log.user_id),
        "workDate": str(log.work_date),
        "checkinAt": log.checkin_at.isoformat() if log.checkin_at else None,
        "checkinLat": float(log.checkin_lat) if log.checkin_lat else None,
        "checkinLng": float(log.checkin_lng) if log.checkin_lng else None,
        "checkinAddress": log.checkin_address,
        "checkoutAt": log.checkout_at.isoformat() if log.checkout_at else None,
        "checkoutLat": float(log.checkout_lat) if log.checkout_lat else None,
        "checkoutLng": float(log.checkout_lng) if log.checkout_lng else None,
        "checkoutAddress": log.checkout_address,
        "totalWorkMinutes": log.total_work_minutes,
        "totalWorkHours": round(log.total_work_minutes / 60, 2) if log.total_work_minutes else None,
        "totalDistanceKm": float(log.total_distance_km) if log.total_distance_km else None,
        "totalShopsVisited": log.total_shops_visited,
        "status": log.status,
        "notes": log.notes,
        "autoCutoffApplied": log.auto_cutoff_applied,
        "isCheckedIn": log.checkin_at is not None,
        "isCheckedOut": log.checkout_at is not None,
    }


def serialize_work_log_detail(log: WorkLog) -> dict:
    base = serialize_work_log(log)

    base["locationEvents"] = [
        {
            "id": str(e.id),
            "eventType": e.event_type,
            "latitude": float(e.latitude),
            "longitude": float(e.longitude),
            "accuracy": float(e.accuracy) if e.accuracy else None,
            "address": e.address,
            "recordedAt": e.recorded_at.isoformat() if e.recorded_at else None,
            "shopId": str(e.shop_id) if e.shop_id else None,
            "shopName": e.shop.name if e.shop else None,
        }
        for e in sorted(log.location_events, key=lambda x: x.recorded_at)
    ]

    base["shopVisits"] = [
        {
            "id": str(v.id),
            "shopId": str(v.shop_id),
            "shopName": v.shop.name if v.shop else None,
            "entryAt": v.entry_at.isoformat() if v.entry_at else None,
            "entryLat": float(v.entry_lat) if v.entry_lat else None,
            "entryLng": float(v.entry_lng) if v.entry_lng else None,
            "exitAt": v.exit_at.isoformat() if v.exit_at else None,
            "exitLat": float(v.exit_lat) if v.exit_lat else None,
            "exitLng": float(v.exit_lng) if v.exit_lng else None,
            "durationMinutes": v.duration_minutes,
            "notes": v.notes,
        }
        for v in sorted(log.shop_visits, key=lambda x: x.entry_at)
    ]

    # Route as ordered GPS points for map rendering
    base["routePoints"] = [
        {
            "lat": float(e.latitude),
            "lng": float(e.longitude),
            "recordedAt": e.recorded_at.isoformat() if e.recorded_at else None,
            "eventType": e.event_type,
        }
        for e in sorted(
            [e for e in log.location_events if e.event_type in (
                LocationEventType.location_ping,
                LocationEventType.checkin,
                LocationEventType.checkout,
            )],
            key=lambda x: x.recorded_at
        )
    ]

    return base