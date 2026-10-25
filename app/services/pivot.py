"""Dynamic pivot / cross-tab reports.

Supports several row fields and column fields (nested grouping), several values
(agg:field) in one pivot, date-grain bucketing, multi-select status, and both an Excel
and a JSON rendering. The single-value params (`row_field`, `col_field`, `value_field`,
`agg`) still work for backward compatibility.

Adding a source = one entry in `PIVOT_SOURCES` + a branch in `_load_rows`.
"""
import uuid
from collections import defaultdict
from datetime import date, datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.services import report_data as rd


AGGREGATIONS = ["sum", "count", "count_distinct", "avg", "min", "max"]
_MEASURE_ONLY = {"sum", "avg", "min", "max"}          # value must be a measure
_NEEDS_FIELD = {"sum", "avg", "min", "max", "count_distinct"}  # value must name a field
DATE_GRAINS = ["day", "week", "month", "quarter", "year"]

LIMITS = {"maxRowFields": 3, "maxColFields": 2, "maxValues": 4, "maxCells": 50000}

# ── Source registry ────────────────────────────────────────────────────────────
PIVOT_SOURCES = {
    "orders": {
        "label": "Orders (one row per order)",
        "statusField": "Status",
        "dimensions": [
            "Order Level", "Visit Type", "Type", "Status", "Tenant",
            "Shop", "District", "Executive", "Distributor", "Date",
        ],
        "measures": ["Pieces", "Order Total"],
        "dateDimensions": ["Date"],
    },
    "order_items": {
        "label": "Order line items (one row per product line)",
        "statusField": "Shipment Status",
        "dimensions": [
            "Order Level", "Visit Type", "Type", "Price Type", "Shipment Status",
            "Tenant", "Shop", "District", "Taluk", "Executive", "Distributor",
            "Category", "Set Type", "Size", "Color", "Product", "Booking Date",
        ],
        "measures": ["Pieces", "Unit Price", "Line Total"],
        "dateDimensions": ["Booking Date"],
    },
}

_FILTERS = [
    "tenant_id", "date_from", "date_to", "status", "order_type", "include_children",
    "child_only", "date_basis", "state_id", "district_id", "taluk_id", "shop_id",
    "assigned_executive", "distributor_id",
]


def list_sources() -> list[dict]:
    """Metadata for the frontend to build the pivot form (no hardcoding needed)."""
    out = []
    for key, cfg in PIVOT_SOURCES.items():
        out.append({
            "source": key,
            "label": cfg["label"],
            "dimensions": cfg["dimensions"],
            "measures": cfg["measures"],
            "aggregations": AGGREGATIONS,
            "aggregationRules": {
                "count": "none",
                "count_distinct": "dimension_or_measure",
                "sum": "measure", "avg": "measure", "min": "measure", "max": "measure",
            },
            "dateDimensions": cfg["dateDimensions"],
            "dateGrains": DATE_GRAINS,
            "filters": _FILTERS,
            "limits": LIMITS,
        })
    return out


# ── Loading ─────────────────────────────────────────────────────────────────────

def _order_kwargs(filters: dict) -> dict:
    # status is applied in-memory (to support multi-select), so it's NOT passed here.
    return {
        "date_from": filters.get("date_from"),
        "date_to": filters.get("date_to"),
        "tenant_id": filters.get("tenant_id"),
        "state_id": filters.get("state_id"),
        "district_id": filters.get("district_id"),
        "taluk_id": filters.get("taluk_id"),
        "shop_id": filters.get("shop_id"),
        "distributor_id": filters.get("distributor_id"),
        "assigned_executive": filters.get("assigned_executive"),
        "order_type": filters.get("order_type"),
        "include_children": filters.get("include_children", True),
        "child_only": filters.get("child_only", False),
        "date_basis": filters.get("date_basis", "order"),
    }


async def _load_rows(db: AsyncSession, source: str, filters: dict) -> list[dict]:
    if source == "orders":
        rows = await rd.get_order_archive_data(db, **_order_kwargs(filters))
    elif source == "order_items":
        rows = await rd.get_order_report_data(db, **_order_kwargs(filters))
    else:
        raise AppException(status_code=400, detail=f"Unknown pivot source '{source}'")

    # Multi-select status filter, applied in memory on the status label.
    statuses = filters.get("status")
    if statuses:
        field = PIVOT_SOURCES[source]["statusField"]
        wanted = {s.value if hasattr(s, "value") else str(s) for s in statuses}
        rows = [r for r in rows if str(r.get(field, "")) in wanted]
    return rows


# ── Value specs ──────────────────────────────────────────────────────────────────

def _value_label(agg: str, field: Optional[str]) -> str:
    if agg == "count":
        return "Count"
    if agg == "count_distinct":
        return f"Distinct {field}"
    return f"{agg.title()} of {field}"


def parse_values(values: Optional[list[str]], value_field: Optional[str], agg: str) -> list[dict]:
    """Build the list of value specs from either the repeated `value=<agg>[:<field>]`
    params or the single `value_field` + `agg` form (backward compatible)."""
    specs: list[dict] = []
    if values:
        for raw in values:
            raw = (raw or "").strip()
            if not raw:
                continue
            if ":" in raw:
                a, f = raw.split(":", 1)
                a, f = a.strip(), f.strip() or None
            else:
                a, f = raw.strip(), None
            specs.append({"agg": a, "field": f, "label": _value_label(a, f)})
    else:
        specs.append({"agg": agg, "field": value_field, "label": _value_label(agg, value_field)})
    return specs


# ── Validation ───────────────────────────────────────────────────────────────────

def _validate(cfg: dict, source: str, row_fields: list[str], col_fields: list[str],
              value_specs: list[dict], grain: str) -> None:
    dims = set(cfg["dimensions"])
    measures = set(cfg["measures"])
    if not row_fields:
        raise AppException(status_code=400, detail="At least one row_field is required")
    if len(row_fields) > LIMITS["maxRowFields"]:
        raise AppException(status_code=400, detail=f"Too many row fields (max {LIMITS['maxRowFields']})")
    if len(col_fields) > LIMITS["maxColFields"]:
        raise AppException(status_code=400, detail=f"Too many column fields (max {LIMITS['maxColFields']})")
    if len(value_specs) > LIMITS["maxValues"]:
        raise AppException(status_code=400, detail=f"Too many values (max {LIMITS['maxValues']})")
    for f in row_fields + col_fields:
        if f not in dims:
            raise AppException(status_code=400, detail=f"'{f}' is not a dimension of '{source}'")
    for v in value_specs:
        a, f = v["agg"], v["field"]
        if a not in AGGREGATIONS:
            raise AppException(status_code=400, detail=f"Unknown aggregation '{a}'")
        if a == "count":
            continue
        if not f:
            raise AppException(status_code=400, detail=f"value field is required for '{a}'")
        if a in _MEASURE_ONLY and f not in measures:
            raise AppException(status_code=400, detail=f"'{f}' is not a measure of '{source}'")
        if a == "count_distinct" and f not in dims and f not in measures:
            raise AppException(status_code=400, detail=f"'{f}' is not a field of '{source}'")
    if grain not in DATE_GRAINS:
        raise AppException(status_code=400, detail=f"Unknown date_grain '{grain}'")


# ── Aggregation + key normalisation ──────────────────────────────────────────────

def _aggregate(values: list, agg: str):
    if agg == "count":
        return len(values)
    if agg == "count_distinct":
        return len({v for v in values if v is not None and v != ""})
    nums = [float(v) for v in values if isinstance(v, (int, float))]
    if not nums:
        return 0
    if agg == "sum":
        return round(sum(nums), 2)
    if agg == "avg":
        return round(sum(nums) / len(nums), 2)
    if agg == "min":
        return round(min(nums), 2)
    if agg == "max":
        return round(max(nums), 2)
    return 0


def _date_grain(s: str, grain: str) -> str:
    try:
        d = datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return str(s)
    if grain == "month":
        return f"{d.year:04d}-{d.month:02d}"
    if grain == "year":
        return f"{d.year:04d}"
    if grain == "quarter":
        return f"{d.year:04d}-Q{(d.month - 1) // 3 + 1}"
    if grain == "week":
        iso = d.isocalendar()
        return f"{iso[0]:04d}-W{iso[1]:02d}"
    return str(s)


def _norm(val, field: str, date_dims: set, grain: str) -> str:
    if val is None:
        return "(blank)"
    s = str(val).strip()  # trims labels (fixes leading/trailing spaces, whitespace dups)
    if not s:
        return "(blank)"
    if field in date_dims and grain != "day":
        return _date_grain(s, grain)
    return s


def _cell(bucket: list, v: dict):
    if v["agg"] == "count":
        return len(bucket)
    return _aggregate([r.get(v["field"]) for r in bucket], v["agg"])


# ── Core compute ─────────────────────────────────────────────────────────────────

def compute_pivot(rows: list[dict], cfg: dict, row_fields: list[str], col_fields: list[str],
                  value_specs: list[dict], grain: str) -> dict:
    date_dims = set(cfg["dateDimensions"])

    cell_rows: dict = defaultdict(list)
    row_rows: dict = defaultdict(list)
    col_rows: dict = defaultdict(list)
    row_keys: list = []
    col_keys: list = []
    seen_r, seen_c = set(), set()

    for r in rows:
        rk = tuple(_norm(r.get(f), f, date_dims, grain) for f in row_fields)
        ck = tuple(_norm(r.get(f), f, date_dims, grain) for f in col_fields) if col_fields else ()
        if rk not in seen_r:
            seen_r.add(rk)
            row_keys.append(rk)
        if col_fields and ck not in seen_c:
            seen_c.add(ck)
            col_keys.append(ck)
        cell_rows[(rk, ck)].append(r)
        row_rows[rk].append(r)
        if col_fields:
            col_rows[ck].append(r)

    row_keys.sort()
    col_keys.sort()

    # Size guard (clear error rather than a silent truncation / timeout).
    projected = max(len(row_keys), 1) * max(len(col_keys), 1) * max(len(value_specs), 1)
    if projected > LIMITS["maxCells"]:
        raise AppException(
            status_code=400,
            detail=(f"Pivot too large: {projected} cells exceeds the {LIMITS['maxCells']} limit. "
                    f"Narrow the date range/filters or use fewer fields."),
        )

    columns = [{"key": list(ck), "label": list(ck)} for ck in col_keys]
    out_rows = []
    for rk in row_keys:
        if col_fields:
            cells = [[_cell(cell_rows.get((rk, ck), []), v) for v in value_specs] for ck in col_keys]
        else:
            cells = []
        out_rows.append({
            "key": list(rk),
            "cells": cells,
            "rowTotal": [_cell(row_rows.get(rk, []), v) for v in value_specs],
        })

    column_totals = [[_cell(col_rows.get(ck, []), v) for v in value_specs] for ck in col_keys]
    grand_total = [_cell(rows, v) for v in value_specs]

    return {
        "rowFields": row_fields,
        "colFields": col_fields,
        "values": value_specs,
        "columns": columns,
        "rows": out_rows,
        "columnTotals": column_totals,
        "grandTotal": grand_total,
        "truncated": False,
    }


async def run_pivot(db: AsyncSession, source: str, row_fields: list[str], col_fields: list[str],
                    value_specs: list[dict], grain: str, filters: dict) -> dict:
    cfg = PIVOT_SOURCES.get(source)
    if not cfg:
        raise AppException(status_code=400, detail=f"Unknown pivot source '{source}'")
    _validate(cfg, source, row_fields, col_fields, value_specs, grain)
    rows = await _load_rows(db, source, filters)
    return compute_pivot(rows, cfg, row_fields, col_fields, value_specs, grain)


# ── Excel rendering (flattened: nested headers are concatenated) ─────────────────

def to_excel_rows(result: dict, include_totals: bool = True) -> list[dict]:
    """Flatten the pivot into row-dicts for generate_excel.

    Columns = one per (column-combo × value), with a combined header
    "colval1 / colval2 | <value label>", plus a "Total | <value label>" per value when
    there are column fields. A final TOTAL row carries the column/grand totals.
    """
    row_fields = result["rowFields"]
    values = result["values"]
    columns = result["columns"]
    has_cols = bool(result["colFields"])

    # Build the ordered list of output column headers.
    headers: list[str] = list(row_fields)
    col_value_headers: list[tuple] = []   # (col_index, value_index, header)
    if has_cols:
        for ci, col in enumerate(columns):
            clabel = " / ".join(str(x) for x in col["label"])
            for vi, v in enumerate(values):
                h = f"{clabel} | {v['label']}"
                col_value_headers.append((ci, vi, h))
                headers.append(h)
    total_headers: list[tuple] = []       # (value_index, header)
    for vi, v in enumerate(values):
        h = (f"Total | {v['label']}") if has_cols else v["label"]
        total_headers.append((vi, h))
        if include_totals or not has_cols:
            headers.append(h)

    def _blank_row() -> dict:
        return {h: "" for h in headers}

    out: list[dict] = []
    for row in result["rows"]:
        d = _blank_row()
        for i, f in enumerate(row_fields):
            d[f] = row["key"][i] if i < len(row["key"]) else ""
        for (ci, vi, h) in col_value_headers:
            d[h] = row["cells"][ci][vi]
        for (vi, h) in total_headers:
            if h in d:
                d[h] = row["rowTotal"][vi]
        out.append(d)

    if include_totals and out:
        tr = _blank_row()
        tr[row_fields[0]] = "TOTAL"
        for (ci, vi, h) in col_value_headers:
            tr[h] = result["columnTotals"][ci][vi]
        for (vi, h) in total_headers:
            if h in tr:
                tr[h] = result["grandTotal"][vi]
        out.append(tr)

    return out
