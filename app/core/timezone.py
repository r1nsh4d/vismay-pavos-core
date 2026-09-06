"""
IST (Asia/Kolkata) helpers for display.

Everything is stored and computed in UTC — DB columns are `timestamptz`, and all
business logic works in UTC. This module only converts UTC datetimes to IST at the
point they're shown to a human (reports, PDFs, etc.). IST is a fixed UTC+5:30 offset
(India does not observe DST), so a plain fixed-offset timezone is enough — no zoneinfo
database needed.
"""
from datetime import datetime, date, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))


def to_ist(dt: datetime | None) -> datetime | None:
    """Convert a datetime to IST. Naive datetimes are assumed to already be UTC
    (matches how this app stores everything), so they're stamped UTC before converting."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)


def fmt_ist(dt: datetime | None, fmt: str = "%Y-%m-%d %H:%M") -> str:
    """Format a UTC datetime as an IST string, blank if not set."""
    ist = to_ist(dt)
    return ist.strftime(fmt) if ist else ""


def ist_today() -> date:
    """Today's calendar date in IST (not the server/UTC date)."""
    return datetime.now(IST).date()


def ist_day_start_utc(d: date) -> datetime:
    """UTC instant for 00:00:00 IST on calendar date `d` — use as an inclusive lower
    bound (>=) when filtering a timestamptz column by an IST calendar date."""
    return datetime(d.year, d.month, d.day, tzinfo=IST).astimezone(timezone.utc)


def ist_day_end_utc(d: date) -> datetime:
    """UTC instant for 23:59:59.999999 IST on calendar date `d` — use as an inclusive
    upper bound (<=) when filtering a timestamptz column by an IST calendar date."""
    return datetime(d.year, d.month, d.day, 23, 59, 59, 999999, tzinfo=IST).astimezone(timezone.utc)


def ist_month_bounds_utc(year: int, month: int) -> tuple[datetime, datetime]:
    """Half-open [start, end) UTC range for a calendar month as reckoned in IST."""
    start = datetime(year, month, 1, tzinfo=IST)
    end = datetime(year + 1, 1, 1, tzinfo=IST) if month == 12 else datetime(year, month + 1, 1, tzinfo=IST)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)
