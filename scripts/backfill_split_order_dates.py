"""One-time backfill: re-date existing split-CHILD orders to their ROOT order's date.

Problem it fixes
----------------
A split child used to be stamped with `created_at` = the moment the split happened.
Since the orders report filters on `created_at`, a child split/billed in a later month
drifted into that later month's report — looking like a fresh order that "arrived" then,
when commercially it is just a later shipment of an order placed earlier.

This walks every child up its `parent_order_id` chain to the root order and sets the
child's `created_at` to the root's `created_at`, so the whole split family reports in the
month the original order arrived. The split moment is preserved separately in `placed_at`,
so no audit information is lost. Parent/root orders are left untouched.

Safe to re-run — rows already matching their root's date are updated to the same value.

Run once inside the app container:

    docker exec -e PYTHONPATH=/app vismay_app python scripts/backfill_split_order_dates.py
"""
import asyncio
import os
import sys

# Make `app` importable when run as `python scripts/backfill_split_order_dates.py`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.database import AsyncSessionLocal


BACKFILL_SQL = text("""
WITH RECURSIVE roots AS (
    -- root orders: carry their own id + date downward
    SELECT id, parent_order_id, created_at, id AS root_id, created_at AS root_created_at
    FROM orders
    WHERE parent_order_id IS NULL
    UNION ALL
    -- each child picks up its root's id + date from its parent
    SELECT o.id, o.parent_order_id, o.created_at, r.root_id, r.root_created_at
    FROM orders o
    JOIN roots r ON o.parent_order_id = r.id
)
UPDATE orders o
SET created_at = rc.root_created_at
FROM roots rc
WHERE o.id = rc.id
  AND o.parent_order_id IS NOT NULL          -- children only
  AND o.created_at IS DISTINCT FROM rc.root_created_at;
""")


async def main() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(BACKFILL_SQL)
        await db.commit()
        # rowcount is the number of child orders re-dated
        print(f"Backfill complete: {result.rowcount} split-child orders re-dated to their root order's date.")


if __name__ == "__main__":
    asyncio.run(main())
