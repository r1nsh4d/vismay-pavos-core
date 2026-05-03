import uuid
from typing import Optional, List
from datetime import datetime, date
from app.models.attendance import AttendanceStatus, LocationEventType
from app.schemas.base import CamelModel


# ── Inputs ─────────────────────────────────────────────────────────────────────

class CheckInInput(CamelModel):
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    address: Optional[str] = None


class CheckOutInput(CamelModel):
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class LocationPingInput(CamelModel):
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    recorded_at: Optional[datetime] = None  # if None, uses server time


class ShopEntryInput(CamelModel):
    shop_id: uuid.UUID
    latitude: float
    longitude: float
    accuracy: Optional[float] = None


class ShopExitInput(CamelModel):
    shop_id: uuid.UUID
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    notes: Optional[str] = None


# ── Responses ──────────────────────────────────────────────────────────────────

class LocationEventResponse(CamelModel):
    id: uuid.UUID
    event_type: LocationEventType
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    address: Optional[str] = None
    recorded_at: datetime
    shop_id: Optional[uuid.UUID] = None
    shop_name: Optional[str] = None


class ShopVisitResponse(CamelModel):
    id: uuid.UUID
    shop_id: uuid.UUID
    shop_name: Optional[str] = None
    entry_at: datetime
    exit_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    notes: Optional[str] = None


class WorkLogResponse(CamelModel):
    id: uuid.UUID
    user_id: uuid.UUID
    work_date: date
    checkin_at: Optional[datetime] = None
    checkin_lat: Optional[float] = None
    checkin_lng: Optional[float] = None
    checkin_address: Optional[str] = None
    checkout_at: Optional[datetime] = None
    checkout_lat: Optional[float] = None
    checkout_lng: Optional[float] = None
    checkout_address: Optional[str] = None
    total_work_minutes: Optional[int] = None
    total_distance_km: Optional[float] = None
    total_shops_visited: Optional[int] = None
    status: AttendanceStatus
    notes: Optional[str] = None
    auto_cutoff_applied: bool = False


class WorkLogDetailResponse(WorkLogResponse):
    location_events: List[LocationEventResponse] = []
    shop_visits: List[ShopVisitResponse] = []


class TravelAllowanceSummary(CamelModel):
    user_id: uuid.UUID
    user_name: str
    month: int
    year: int
    total_days_worked: int
    total_distance_km: float
    total_work_hours: float
    total_shops_visited: int
    daily_breakdown: List[dict] = []