import uuid
import enum
from typing import Optional
from sqlalchemy import String, ForeignKey, Boolean, Numeric, Integer, Enum, Text, DateTime, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class AttendanceStatus(str, enum.Enum):
    present = "present"
    absent = "absent"
    half_day = "half_day"
    holiday = "holiday"


class LocationEventType(str, enum.Enum):
    checkin = "checkin"           # start of work day
    checkout = "checkout"         # end of work day
    shop_entry = "shop_entry"     # entered a shop
    shop_exit = "shop_exit"       # exited a shop
    location_ping = "location_ping"  # periodic GPS ping (every 5 min)


class WorkLog(BaseModel):
    """One record per work day per executive."""
    __tablename__ = "work_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    work_date: Mapped[str] = mapped_column(Date, nullable=False, index=True)

    # Check-in
    checkin_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
    checkin_lat: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)
    checkin_lng: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)
    checkin_address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Check-out
    checkout_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
    checkout_lat: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)
    checkout_lng: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)
    checkout_address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Computed at checkout or end of day
    total_work_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_distance_km: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
    total_shops_visited: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)

    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, native_enum=False),
        default=AttendanceStatus.present,
        nullable=False,
    )

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Auto cutoff applied?
    auto_cutoff_applied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    user = relationship("User", backref="work_logs")
    location_events = relationship("LocationEvent", back_populates="work_log", cascade="all, delete-orphan")
    shop_visits = relationship("ShopVisit", back_populates="work_log", cascade="all, delete-orphan")


class LocationEvent(BaseModel):
    """Every GPS ping and checkin/checkout event."""
    __tablename__ = "location_events"

    work_log_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_logs.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )

    event_type: Mapped[LocationEventType] = mapped_column(
        Enum(LocationEventType, native_enum=False), nullable=False
    )
    latitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    accuracy: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)  # metres
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    recorded_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # For shop events
    shop_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("shops.id"), nullable=True
    )

    work_log = relationship("WorkLog", back_populates="location_events")
    user = relationship("User", backref="location_events")
    shop = relationship("Shop", backref="location_events")


class ShopVisit(BaseModel):
    """Tracks time spent in each shop per day."""
    __tablename__ = "shop_visits"

    work_log_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_logs.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shops.id"), nullable=False, index=True
    )

    entry_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_lat: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)
    entry_lng: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)

    exit_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_lat: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)
    exit_lng: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)

    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    work_log = relationship("WorkLog", back_populates="shop_visits")
    user = relationship("User", backref="shop_visits")
    shop = relationship("Shop", backref="shop_visits")