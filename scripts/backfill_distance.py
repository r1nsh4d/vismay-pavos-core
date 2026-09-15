"""One-time backfill: recompute `total_distance_km` for completed (checked-out) work logs
using the current point-to-point distance calculation.

Only checked-out days are touched — open / never-checked-out days are left blank on purpose.
Existing values are overwritten with the freshly-computed distance (fixes days that were
previously stored as 0 because the accuracy filter dropped every ping).

Run once inside the app container:

    docker exec vismay_app python scripts/backfill_distance.py
"""
import asyncio
import os
import sys

# Make `app` importable when run as `python scripts/backfill_distance.py` (adds the repo
# root to the path, since Python otherwise only puts the scripts/ folder on sys.path).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.attendance import WorkLog
from app.services.attendance import _calculate_total_distance


async def main() -> None:
    async with AsyncSessionLocal() as db:
        logs = (await db.execute(
            select(WorkLog).where(
                WorkLog.is_deleted == False,          # noqa: E712
                WorkLog.checkout_at.isnot(None),       # completed days only
            )
        )).scalars().all()

        updated = 0
        for log in logs:
            new_dist = await _calculate_total_distance(db, log.id)
            old = float(log.total_distance_km) if log.total_distance_km is not None else None
            if old != new_dist:
                log.total_distance_km = new_dist
                updated += 1

        await db.commit()
        print(f"Backfill complete: {len(logs)} checked-out work logs recomputed, {updated} updated.")


if __name__ == "__main__":
    asyncio.run(main())
