import uuid
from collections import defaultdict
from datetime import datetime, date
from typing import Optional
from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order, OrderItem, OrderReturn, OrderStatus, OrderType, PriceType
from app.models.product import Product, ProductVariant
from app.models.stock import Stock, BundleStock
from app.models.user import User, UserDistrict, UserTenant
from app.models.district import District
from app.models.states import State
from app.models.taluk import Taluk
from app.models.shop import Shop
from app.models.target import ExecutiveTarget, TargetType
from app.models.set_type import SetType
from app.models.category import Category
from app.models.role import Role
from app.models.tenant import Tenant
from app.services.orders import _distributor_name


# ── Helpers ────────────────────────────────────────────────────────────────────

def _date_filters(query, model, date_from, date_to):
    if date_from:
        query = query.where(model.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        query = query.where(model.created_at <= datetime.combine(date_to, datetime.max.time()))
    return query


async def _get_tenant_categories(db: AsyncSession, tenant_id: uuid.UUID) -> list[Category]:
    result = await db.execute(
        select(Category).where(
            Category.tenant_id == tenant_id,
            Category.is_deleted == False,
            Category.is_active == True,
        ).order_by(Category.name)
    )
    return result.scalars().all()


# ── Order Summary ──────────────────────────────────────────────────────────────

async def get_order_summary(
    db: AsyncSession,
    tenant_id: Optional[uuid.UUID] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    base = [Order.is_deleted == False, Order.parent_order_id == None]  # noqa
    if tenant_id:
        base.append(Order.tenant_id == tenant_id)
    if date_from:
        base.append(Order.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        base.append(Order.created_at <= datetime.combine(date_to, datetime.max.time()))

    total_q = await db.execute(
        select(func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0)).where(*base)
    )
    total_count, total_value = total_q.one()

    status_q = await db.execute(
        select(Order.status, func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0))
        .where(*base)
        .group_by(Order.status)
    )
    by_status = [
        {"status": row[0], "count": row[1], "totalValue": float(row[2])}
        for row in status_q.all()
    ]

    type_q = await db.execute(
        select(Order.order_type, func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0))
        .where(*base)
        .group_by(Order.order_type)
    )
    by_type = [
        {"orderType": row[0], "count": row[1], "totalValue": float(row[2])}
        for row in type_q.all()
    ]

    price_q = await db.execute(
        select(Order.price_type, func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0))
        .where(*base)
        .group_by(Order.price_type)
    )
    by_price_type = [
        {"priceType": row[0], "count": row[1], "totalValue": float(row[2])}
        for row in price_q.all()
    ]

    return {
        "totalOrders": total_count,
        "totalValue": float(total_value),
        "byStatus": by_status,
        "byType": by_type,
        "byPriceType": by_price_type,
    }


# ── Order Consolidation Report ─────────────────────────────────────────────────

async def get_order_consolidation_report(
    db: AsyncSession,
    tenant_id: Optional[uuid.UUID] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    """
    Generates consolidation report matching images 1 & 2.
    Rows = status groups, Columns = tenant categories with qty and value.
    """
    if tenant_id:
        categories = await _get_tenant_categories(db, tenant_id)
    else:
        result = await db.execute(
            select(Category).where(
                Category.is_deleted == False,
                Category.is_active == True,
            ).order_by(Category.name)
        )
        categories = result.scalars().all()

    base_filters = [Order.is_deleted == False, Order.parent_order_id == None]  # noqa
    if tenant_id:
        base_filters.append(Order.tenant_id == tenant_id)
    if date_from:
        base_filters.append(Order.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        base_filters.append(Order.created_at <= datetime.combine(date_to, datetime.max.time()))

    async def get_stats_for_statuses(status_list: list) -> tuple[dict, int]:
        if not status_list:
            return {}, 0

        filters = base_filters + [Order.status.in_(status_list)]

        result = await db.execute(
            select(
                Product.category_id,
                func.sum(OrderItem.count).label("total_qty"),
                func.sum(OrderItem.total_price).label("total_value"),
            )
            .join(OrderItem, OrderItem.order_id == Order.id)
            .join(Product, Product.id == OrderItem.product_id)
            .where(*filters)
            .group_by(Product.category_id)
        )
        stats = {
            str(row.category_id): {
                "qty": int(row.total_qty or 0),
                "value": round(float(row.total_value or 0) / 100000, 2),
            }
            for row in result.all()
        }

        shop_result = await db.execute(
            select(func.count(func.distinct(Order.shop_id))).where(*filters)
        )
        shops = shop_result.scalar() or 0

        return stats, shops

    status_groups = [
        ("TOTAL ORDER", [
            OrderStatus.placed, OrderStatus.verified, OrderStatus.assigned,
            OrderStatus.approved, OrderStatus.on_hold, OrderStatus.estimated,
            OrderStatus.billed, OrderStatus.packing, OrderStatus.dispatched,
            OrderStatus.delivered, OrderStatus.partially_returned,
            OrderStatus.returned, OrderStatus.rejected, OrderStatus.cancelled,
        ]),
        ("TOTAL BILLED", [
            OrderStatus.billed, OrderStatus.packing, OrderStatus.dispatched,
            OrderStatus.delivered, OrderStatus.partially_returned, OrderStatus.returned,
        ]),
        ("HOLD", [OrderStatus.on_hold]),
        ("EXECUTIVE HOLD", [OrderStatus.placed, OrderStatus.verified]),
        ("OUT OF STOCK", [OrderStatus.estimated]),
        ("BALANCE TO BILL", [OrderStatus.approved]),
        ("CANCELLED", [OrderStatus.cancelled]),
        ("REJECTED", [OrderStatus.rejected]),
    ]

    report_rows = []
    for group_name, statuses in status_groups:
        cat_stats, shops = await get_stats_for_statuses(statuses)

        row = {
            "group": group_name,
            "noOfCounters": shops,
            "categories": {},
            "totalQty": 0,
            "totalValue": 0.0,
        }

        for cat in categories:
            key = str(cat.id)
            stats = cat_stats.get(key, {"qty": 0, "value": 0.0})
            row["categories"][cat.name] = stats
            row["totalQty"] += stats["qty"]
            row["totalValue"] += stats["value"]

        row["totalValue"] = round(row["totalValue"], 2)
        report_rows.append(row)

    tenant_name = ""
    if tenant_id:
        tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id))
        tenant_name = tenant.name if tenant else ""

    return {
        "generatedAt": datetime.now().strftime("%d-%m-%Y"),
        "tenantName": tenant_name,
        "categories": [c.name for c in categories],
        "rows": report_rows,
    }


def _build_consolidation_excel(report: dict, title: str) -> bytes:
    import io
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Consolidation"

    categories = report["categories"]
    generated_at = report["generatedAt"]
    n_cats = len(categories)

    total_cols = 2 + (n_cats * 2) + 2
    qty_start = 3
    qty_end = qty_start + n_cats - 1
    val_start = qty_end + 1
    val_end = val_start + n_cats - 1
    total_qty_col = val_end + 1
    total_val_col = total_qty_col + 1

    title_fill = PatternFill(start_color="6B1A2B", end_color="6B1A2B", fill_type="solid")
    header_fill = PatternFill(start_color="E8B4BC", end_color="E8B4BC", fill_type="solid")
    row_odd = PatternFill(start_color="F2D7DB", end_color="F2D7DB", fill_type="solid")
    row_even = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
    total_order_fill = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")
    billed_fill = PatternFill(start_color="E8B4BC", end_color="E8B4BC", fill_type="solid")

    thin = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_al = Alignment(horizontal="left", vertical="center", wrap_text=True)

    # Row 1: Title
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=total_cols)
    c = ws.cell(row=1, column=1, value=f"{title} AS ON {generated_at}")
    c.fill = title_fill
    c.font = Font(bold=True, color="FFFFFF", size=16)
    c.alignment = center
    ws.row_dimensions[1].height = 45

    # Row 2: Section headers
    ws.merge_cells(start_row=2, start_column=1, end_row=3, end_column=1)
    c = ws.cell(row=2, column=1, value="PRODUCTS")
    c.fill = header_fill
    c.font = Font(bold=True, size=10)
    c.alignment = center
    c.border = thin

    ws.merge_cells(start_row=2, start_column=2, end_row=3, end_column=2)
    c = ws.cell(row=2, column=2, value="NO.OF\nCOUNTERS")
    c.fill = header_fill
    c.font = Font(bold=True, size=10)
    c.alignment = center
    c.border = thin

    ws.merge_cells(start_row=2, start_column=qty_start, end_row=2, end_column=qty_end)
    c = ws.cell(row=2, column=qty_start, value="IN QUANTITY")
    c.fill = header_fill
    c.font = Font(bold=True, size=10)
    c.alignment = center
    c.border = thin

    ws.merge_cells(start_row=2, start_column=val_start, end_row=2, end_column=val_end)
    c = ws.cell(row=2, column=val_start, value="IN VALUE")
    c.fill = header_fill
    c.font = Font(bold=True, size=10)
    c.alignment = center
    c.border = thin

    ws.merge_cells(start_row=2, start_column=total_qty_col, end_row=3, end_column=total_qty_col)
    c = ws.cell(row=2, column=total_qty_col, value="TOTAL")
    c.fill = header_fill
    c.font = Font(bold=True, size=10)
    c.alignment = center
    c.border = thin

    ws.merge_cells(start_row=2, start_column=total_val_col, end_row=3, end_column=total_val_col)
    c = ws.cell(row=2, column=total_val_col, value="TOTAL\nVALUE")
    c.fill = header_fill
    c.font = Font(bold=True, size=10)
    c.alignment = center
    c.border = thin

    # Row 3: Category sub-headers
    for i, cat_name in enumerate(categories):
        c = ws.cell(row=3, column=qty_start + i, value=cat_name.upper())
        c.fill = header_fill
        c.font = Font(bold=True, size=9)
        c.alignment = center
        c.border = thin

        c = ws.cell(row=3, column=val_start + i, value=cat_name.upper())
        c.fill = header_fill
        c.font = Font(bold=True, size=9)
        c.alignment = center
        c.border = thin

    ws.row_dimensions[2].height = 20
    ws.row_dimensions[3].height = 20

    # Data rows
    for row_idx, row_data in enumerate(report["rows"], start=4):
        is_total = row_data["group"] == "TOTAL ORDER"
        is_billed = row_data["group"] == "TOTAL BILLED"

        if is_total:
            fill = total_order_fill
            font_color = "FFFFFF"
        elif is_billed:
            fill = billed_fill
            font_color = "000000"
        else:
            fill = row_odd if row_idx % 2 == 0 else row_even
            font_color = "000000"

        font = Font(bold=is_total or is_billed, size=10, color=font_color)
        num_font = Font(bold=is_total or is_billed, size=9, color=font_color)

        c = ws.cell(row=row_idx, column=1, value=row_data["group"])
        c.fill = fill
        c.font = font
        c.alignment = left_al
        c.border = thin

        c = ws.cell(row=row_idx, column=2, value=row_data["noOfCounters"])
        c.fill = fill
        c.font = num_font
        c.alignment = center
        c.border = thin

        for i, cat_name in enumerate(categories):
            cat_data = row_data["categories"].get(cat_name, {"qty": 0, "value": 0.0})

            c = ws.cell(row=row_idx, column=qty_start + i, value=cat_data["qty"])
            c.fill = fill
            c.font = num_font
            c.alignment = center
            c.border = thin

            c = ws.cell(row=row_idx, column=val_start + i, value=cat_data["value"])
            c.fill = fill
            c.font = num_font
            c.alignment = center
            c.border = thin

        c = ws.cell(row=row_idx, column=total_qty_col, value=row_data["totalQty"])
        c.fill = fill
        c.font = Font(bold=True, size=10, color=font_color)
        c.alignment = center
        c.border = thin

        c = ws.cell(row=row_idx, column=total_val_col, value=round(row_data["totalValue"], 2))
        c.fill = fill
        c.font = Font(bold=True, size=10, color=font_color)
        c.alignment = center
        c.border = thin

        ws.row_dimensions[row_idx].height = 24

    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 12
    for i in range(n_cats * 2 + 2):
        ws.column_dimensions[get_column_letter(qty_start + i)].width = 14

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── Executive Wise Report ──────────────────────────────────────────────────────

async def get_executive_wise_report(
    db: AsyncSession,
    year: int,
    month: int,
    tenant_id: Optional[uuid.UUID] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    """
    Generates executive wise report matching images 3 & 4.
    Rows = executives with districts, Columns = categories with target/order/hold/acvmt/%
    """
    if tenant_id:
        categories = await _get_tenant_categories(db, tenant_id)
    else:
        result = await db.execute(
            select(Category).where(
                Category.is_deleted == False,
                Category.is_active == True,
            ).order_by(Category.name)
        )
        categories = result.scalars().all()

    exec_query = (
        select(User)
        .where(User.is_deleted == False, User.is_active == True)
        .join(User.role)
        .where(Role.name == "executive")
        .options(
            selectinload(User.user_districts).selectinload(UserDistrict.district)
        )
        .order_by(User.first_name)
    )
    if tenant_id:
        exec_query = exec_query.where(
            User.user_tenants.any(UserTenant.tenant_id == tenant_id)
        )

    exec_result = await db.execute(exec_query)
    executives = exec_result.scalars().unique().all()

    excluded = [OrderStatus.rejected, OrderStatus.cancelled]

    date_filters = []
    if date_from:
        date_filters.append(Order.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        date_filters.append(Order.created_at <= datetime.combine(date_to, datetime.max.time()))
    if not date_from and not date_to:
        date_filters.append(extract("year", Order.created_at) == year)
        date_filters.append(extract("month", Order.created_at) == month)

    exec_rows = []
    cat_totals = {str(c.id): {"target": 0, "order": 0, "hold": 0, "acvmt": 0} for c in categories}
    grand = {"target": 0, "order": 0, "hold": 0, "acvmt": 0}

    for exe in executives:
        districts = [ud.district for ud in exe.user_districts if ud.district]

        targets_result = await db.execute(
            select(ExecutiveTarget).where(
                ExecutiveTarget.user_id == exe.id,
                ExecutiveTarget.year == year,
                ExecutiveTarget.month == month,
                ExecutiveTarget.target_type == TargetType.category_quantity,
            )
        )
        target_by_cat = {
            str(t.category_id): float(t.target_value)
            for t in targets_result.scalars().all()
        }

        order_result = await db.execute(
            select(
                Product.category_id,
                func.sum(OrderItem.count).label("qty"),
            )
            .join(OrderItem, OrderItem.product_id == Product.id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                Order.assigned_executive == exe.id,
                Order.is_deleted == False,
                Order.status.not_in(excluded),
                Order.parent_order_id == None,  # noqa
                *date_filters,
            )
            .group_by(Product.category_id)
        )
        order_by_cat = {str(r.category_id): int(r.qty or 0) for r in order_result.all()}

        hold_result = await db.execute(
            select(
                Product.category_id,
                func.sum(OrderItem.count).label("qty"),
            )
            .join(OrderItem, OrderItem.product_id == Product.id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                Order.assigned_executive == exe.id,
                Order.is_deleted == False,
                Order.status == OrderStatus.on_hold,
                Order.parent_order_id == None,  # noqa
                *date_filters,
            )
            .group_by(Product.category_id)
        )
        hold_by_cat = {str(r.category_id): int(r.qty or 0) for r in hold_result.all()}

        cat_data = {}
        exe_totals = {"target": 0, "order": 0, "hold": 0, "acvmt": 0}

        for cat in categories:
            cid = str(cat.id)
            target = int(target_by_cat.get(cid, 0))
            order_qty = order_by_cat.get(cid, 0)
            hold_qty = hold_by_cat.get(cid, 0)
            acvmt = order_qty - hold_qty
            pct = round((acvmt / target * 100), 0) if target else 0

            cat_data[cat.name] = {
                "target": target,
                "order": order_qty,
                "hold": hold_qty,
                "acvmt": acvmt,
                "pct": int(pct),
            }

            exe_totals["target"] += target
            exe_totals["order"] += order_qty
            exe_totals["hold"] += hold_qty
            exe_totals["acvmt"] += acvmt

            cat_totals[cid]["target"] += target
            cat_totals[cid]["order"] += order_qty
            cat_totals[cid]["hold"] += hold_qty
            cat_totals[cid]["acvmt"] += acvmt

        grand["target"] += exe_totals["target"]
        grand["order"] += exe_totals["order"]
        grand["hold"] += exe_totals["hold"]
        grand["acvmt"] += exe_totals["acvmt"]

        total_pct = round((exe_totals["acvmt"] / exe_totals["target"] * 100), 0) if exe_totals["target"] else 0

        exec_rows.append({
            "slNo": len(exec_rows) + 1,
            "executive": f"{exe.first_name} {exe.last_name}".strip(),
            "districts": [d.name for d in districts] if districts else [""],
            "categories": cat_data,
            "totalTarget": exe_totals["target"],
            "totalOrder": exe_totals["order"],
            "totalHold": exe_totals["hold"],
            "totalAcvmt": exe_totals["acvmt"],
            "totalPct": int(total_pct),
        })

    tenant_name = ""
    if tenant_id:
        tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id))
        tenant_name = tenant.name if tenant else ""

    return {
        "generatedAt": datetime.now().strftime("%d-%m-%Y"),
        "tenantName": tenant_name,
        "year": year,
        "month": month,
        "categories": [c.name for c in categories],
        "rows": exec_rows,
        "categoryTotals": {
            cat.name: cat_totals[str(cat.id)] for cat in categories
        },
        "grandTotals": grand,
    }


def _build_executive_wise_excel(report: dict, title: str) -> bytes:
    import io
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Executive Wise"

    categories = report["categories"]
    generated_at = report["generatedAt"]
    tenant_name = report.get("tenantName", "")
    n_cats = len(categories)

    cols_per_cat = 5
    fixed = 3
    total_summary = 5
    total_cols = fixed + (n_cats * cols_per_cat) + total_summary

    title_fill = PatternFill(start_color="2E4057", end_color="2E4057", fill_type="solid")
    header_fill = PatternFill(start_color="BDD7EE", end_color="BDD7EE", fill_type="solid")
    green_fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
    white_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
    district_fill = PatternFill(start_color="F9F9F9", end_color="F9F9F9", fill_type="solid")
    total_fill = PatternFill(start_color="FFC000", end_color="FFC000", fill_type="solid")

    thin = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_al = Alignment(horizontal="left", vertical="center")

    full_title = f"{tenant_name} - {title} - EXECUTIVE WISE AS ON {generated_at}"

    # Row 1: Title
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=total_cols)
    c = ws.cell(row=1, column=1, value=full_title)
    c.fill = title_fill
    c.font = Font(bold=True, color="FFFFFF", size=12)
    c.alignment = center
    ws.row_dimensions[1].height = 30

    # Rows 2-3: Headers
    for col, val in [(1, "SL. NO"), (2, "EXECUTIVE"), (3, "DISTRICT")]:
        ws.merge_cells(start_row=2, start_column=col, end_row=3, end_column=col)
        c = ws.cell(row=2, column=col, value=val)
        c.fill = header_fill
        c.font = Font(bold=True, size=9)
        c.alignment = center
        c.border = thin

    for i, cat_name in enumerate(categories):
        col_start = fixed + 1 + (i * cols_per_cat)
        col_end = col_start + cols_per_cat - 1

        ws.merge_cells(start_row=2, start_column=col_start, end_row=2, end_column=col_end)
        c = ws.cell(row=2, column=col_start, value=cat_name.upper())
        c.fill = header_fill
        c.font = Font(bold=True, size=9)
        c.alignment = center
        c.border = thin

        for j, sub in enumerate(["TARGET", "ORDER", "HOLD", "ACVMT", "%"]):
            c = ws.cell(row=3, column=col_start + j, value=sub)
            c.fill = header_fill
            c.font = Font(bold=True, size=8)
            c.alignment = center
            c.border = thin

    total_start = fixed + 1 + (n_cats * cols_per_cat)
    ws.merge_cells(start_row=2, start_column=total_start, end_row=2, end_column=total_start + total_summary - 1)
    c = ws.cell(row=2, column=total_start, value="TOTAL")
    c.fill = header_fill
    c.font = Font(bold=True, size=9)
    c.alignment = center
    c.border = thin

    for j, sub in enumerate(["TARGET", "ORDER", "HOLD", "ACVMT", "%"]):
        c = ws.cell(row=3, column=total_start + j, value=sub)
        c.fill = header_fill
        c.font = Font(bold=True, size=8)
        c.alignment = center
        c.border = thin

    ws.row_dimensions[2].height = 16
    ws.row_dimensions[3].height = 16

    # Data rows
    current_row = 4
    for exe_data in report["rows"]:
        districts = exe_data["districts"] or [""]
        n_dist = len(districts)
        fill = green_fill if exe_data["slNo"] % 2 == 0 else white_fill

        for d_idx, dist_name in enumerate(districts):
            is_first = d_idx == 0

            if is_first:
                if n_dist > 1:
                    ws.merge_cells(start_row=current_row, start_column=1,
                                   end_row=current_row + n_dist - 1, end_column=1)
                c = ws.cell(row=current_row, column=1, value=exe_data["slNo"])
                c.fill = fill
                c.font = Font(bold=True, size=9)
                c.alignment = center
                c.border = thin

                if n_dist > 1:
                    ws.merge_cells(start_row=current_row, start_column=2,
                                   end_row=current_row + n_dist - 1, end_column=2)
                c = ws.cell(row=current_row, column=2, value=exe_data["executive"])
                c.fill = fill
                c.font = Font(bold=True, size=9)
                c.alignment = center
                c.border = thin

            c = ws.cell(row=current_row, column=3, value=dist_name)
            c.fill = fill if is_first else district_fill
            c.font = Font(size=8)
            c.alignment = left_al
            c.border = thin

            if is_first:
                for i, cat_name in enumerate(categories):
                    col_start = fixed + 1 + (i * cols_per_cat)
                    cdata = exe_data["categories"].get(cat_name, {
                        "target": 0, "order": 0, "hold": 0, "acvmt": 0, "pct": 0
                    })
                    vals = [
                        cdata["target"], cdata["order"],
                        cdata["hold"], cdata["acvmt"],
                        f"{cdata['pct']}%"
                    ]
                    for j, val in enumerate(vals):
                        col = col_start + j
                        if n_dist > 1:
                            ws.merge_cells(
                                start_row=current_row, start_column=col,
                                end_row=current_row + n_dist - 1, end_column=col
                            )
                        c = ws.cell(row=current_row, column=col, value=val)
                        c.fill = fill
                        c.font = Font(size=8)
                        c.alignment = center
                        c.border = thin

                total_vals = [
                    exe_data["totalTarget"], exe_data["totalOrder"],
                    exe_data["totalHold"], exe_data["totalAcvmt"],
                    f"{exe_data['totalPct']}%"
                ]
                for j, val in enumerate(total_vals):
                    col = total_start + j
                    if n_dist > 1:
                        ws.merge_cells(
                            start_row=current_row, start_column=col,
                            end_row=current_row + n_dist - 1, end_column=col
                        )
                    c = ws.cell(row=current_row, column=col, value=val)
                    c.fill = fill
                    c.font = Font(bold=True, size=8)
                    c.alignment = center
                    c.border = thin
            else:
                for col in range(fixed + 1, total_cols + 1):
                    ws.cell(row=current_row, column=col).border = thin

            ws.row_dimensions[current_row].height = 15
            current_row += 1

    # TOTAL row
    ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=2)
    c = ws.cell(row=current_row, column=1, value="TOTAL")
    c.fill = total_fill
    c.font = Font(bold=True, size=10)
    c.alignment = center
    c.border = thin

    ws.cell(row=current_row, column=3, value="").fill = total_fill
    ws.cell(row=current_row, column=3).border = thin

    cat_totals = report["categoryTotals"]
    grand = report["grandTotals"]

    for i, cat_name in enumerate(categories):
        col_start = fixed + 1 + (i * cols_per_cat)
        ct = cat_totals.get(cat_name, {"target": 0, "order": 0, "hold": 0, "acvmt": 0})
        pct = round((ct["acvmt"] / ct["target"] * 100), 0) if ct["target"] else 0
        vals = [ct["target"], ct["order"], ct["hold"], ct["acvmt"], f"{int(pct)}%"]
        for j, val in enumerate(vals):
            c = ws.cell(row=current_row, column=col_start + j, value=val)
            c.fill = total_fill
            c.font = Font(bold=True, size=9)
            c.alignment = center
            c.border = thin

    grand_pct = round((grand["acvmt"] / grand["target"] * 100), 0) if grand["target"] else 0
    for j, val in enumerate([
        grand["target"], grand["order"],
        grand["hold"], grand["acvmt"],
        f"{int(grand_pct)}%"
    ]):
        c = ws.cell(row=current_row, column=total_start + j, value=val)
        c.fill = total_fill
        c.font = Font(bold=True, size=9)
        c.alignment = center
        c.border = thin

    ws.row_dimensions[current_row].height = 22

    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 18
    for i in range(n_cats * cols_per_cat + total_summary):
        ws.column_dimensions[get_column_letter(fixed + 1 + i)].width = 9

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── Order Detail Report ────────────────────────────────────────────────────────

def _tat_days(start, end) -> str | float:
    """Turn-around time in days between booking and delivery."""
    if not start or not end:
        return ""
    return round((end - start).total_seconds() / 86400, 1)


def _fmt(dt) -> str:
    """Format a status timestamp, blank if not yet reached."""
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


async def get_order_report_data(
    db: AsyncSession,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    tenant_id: Optional[uuid.UUID] = None,
    state_id: Optional[uuid.UUID] = None,
    district_id: Optional[uuid.UUID] = None,
    taluk_id: Optional[uuid.UUID] = None,
    shop_id: Optional[uuid.UUID] = None,
    distributor_id: Optional[uuid.UUID] = None,
    assigned_executive: Optional[uuid.UUID] = None,
    status: Optional[OrderStatus] = None,
    order_type: Optional[OrderType] = None,
    include_children: bool = True,
) -> list[dict]:
    query = (
        select(Order)
        .where(Order.is_deleted == False)
        .options(
            selectinload(Order.items).selectinload(OrderItem.product).selectinload(Product.category),
            selectinload(Order.items).selectinload(OrderItem.set_type),
            selectinload(Order.items).selectinload(OrderItem.variant),
            selectinload(Order.shop).selectinload(Shop.district),
            selectinload(Order.shop).selectinload(Shop.taluk),
            selectinload(Order.executive),
            selectinload(Order.distributor),
            selectinload(Order.tenant),
        )
    )

    # Parent orders only when children are excluded; by default split children are included
    # so their moved-out items/amounts are counted (parent + child together = original total).
    if not include_children:
        query = query.where(Order.parent_order_id == None)  # noqa

    query = _date_filters(query, Order, date_from, date_to)

    if tenant_id:
        query = query.where(Order.tenant_id == tenant_id)
    if shop_id:
        query = query.where(Order.shop_id == shop_id)
    if distributor_id:
        query = query.where(Order.distributor_id == distributor_id)
    if assigned_executive:
        query = query.where(Order.assigned_executive == assigned_executive)
    if status:
        query = query.where(Order.status == status)
    if order_type:
        query = query.where(Order.order_type == order_type)

    if district_id or taluk_id or state_id:
        query = query.join(Order.shop)
        if district_id:
            query = query.where(Shop.district_id == district_id)
        if taluk_id:
            query = query.where(Shop.taluk_id == taluk_id)
        if state_id:
            query = query.join(Shop.district).where(District.state_id == state_id)

    result = await db.execute(query.order_by(Order.created_at.desc()))
    orders = result.scalars().unique().all()

    rows = []
    for o in orders:
        booking_dt = o.dispatched_at
        price_label = o.price_type.value.upper()
        if price_label == "MRP":
            price_label = "MRP(Net Of Tax)"

        order_head = {
            "Order Number": o.order_number,
            "Bill Number": o.bill_number or "",
            "Type": o.order_type.value,
            "Price Type": o.price_type.value,
            "Shipment Status": o.status.value,
            "Tenant": o.tenant.name if o.tenant else "",
            "Shop": o.shop.name if o.shop else "",
            "District": o.shop.district.name if (o.shop and o.shop.district) else "",
            "Taluk": o.shop.taluk.name if (o.shop and o.shop.taluk) else "",
            "Executive": f"{o.executive.first_name} {o.executive.last_name}".strip() if o.executive else "",
            "Distributor": _distributor_name(o.distributor) if o.distributor else "",
        }
        # tail order-level fields (financial + shipping, after the line block)
        order_tail = {
            "Order Subtotal": float(o.subtotal),
            "Order Discount": float(o.discount_amount),
            "Order Total": float(o.total_amount),
            "Transporter Name": o.delivery_partner or "",
            "Tracking Number": o.tracking_number or "",
            "Boxes Dispatched": o.dispatched_box_count if o.dispatched_box_count is not None else "",
            "Delivery Notes": o.delivery_notes or "",
            # ── Action timestamps (full lifecycle; blank until the stage is reached) ──
            "Placed At": _fmt(o.placed_at),
            "Verified At": _fmt(o.verified_at),
            "Assigned At": _fmt(o.assigned_at),
            "Approved At": _fmt(o.approved_at),
            "Estimated At": _fmt(o.estimated_at),
            "Billed At": _fmt(o.billed_at),
            "Packing At": _fmt(o.packing_at),
            "Dispatched At": _fmt(o.dispatched_at),
            "Delivered At": _fmt(o.delivered_at),
            "Cancelled At": _fmt(o.cancelled_at),
            "Rejected At": _fmt(o.rejected_at),
            "Returned At": _fmt(o.returned_at),
            # ── Summary dates ──
            "Booking Date": booking_dt.strftime("%Y-%m-%d") if booking_dt else "",
            "Delivery Date": _fmt(o.delivered_at),
            # ── Turn-around times ──
            # Warehouse TAT: billed → dispatched (dwell time inside the warehouse).
            # Delivery TAT: dispatched → delivered (transit time).
            "Delivery TAT (days)": _tat_days(booking_dt, o.delivered_at),
        }

        if not o.items:
            rows.append({**order_head, "SL": "", "Product": "", "Category": "",
                         "Set Type": "", "Size": "", "Color": "", "Pieces": 0,
                         "Unit Price": "", "Price Basis": price_label, "Line Total": 0,
                         **order_tail})
            continue

        for idx, item in enumerate(o.items, start=1):
            category = (
                item.product.category.name
                if item.product and item.product.category
                else ""
            )
            rows.append({
                **order_head,
                "SL": idx,
                "Product": item.product.name if item.product else "?",
                "Category": category,
                "Set Type": item.set_type.name if item.set_type else "",
                "Size": item.variant.size if item.variant else "",
                "Color": item.variant.color if item.variant else "",
                "Pieces": item.count or 0,
                "Unit Price": float(item.unit_price or 0),
                "Price Basis": price_label,
                "Line Total": float(item.total_price or 0),
                **order_tail,
            })
    return rows


# ── Stock Reports ──────────────────────────────────────────────────────────────

async def get_stock_report_data(
    db: AsyncSession,
    tenant_id: Optional[uuid.UUID] = None,
    category_id: Optional[uuid.UUID] = None,
    product_id: Optional[uuid.UUID] = None,
) -> list[dict]:
    query = (
        select(ProductVariant)
        .where(ProductVariant.is_deleted == False)
        .options(
            selectinload(ProductVariant.product).selectinload(Product.category),
            selectinload(ProductVariant.stock)
            .selectinload(Stock.bundle_stocks)
            .selectinload(BundleStock.set_type),
        )
        .join(ProductVariant.product)
        .where(Product.is_deleted == False)
    )

    if tenant_id:
        query = query.where(Product.tenant_id == tenant_id)
    if category_id:
        query = query.where(Product.category_id == category_id)
    if product_id:
        query = query.where(ProductVariant.product_id == product_id)

    variants = (await db.execute(query)).scalars().all()

    grouped: dict[str, dict] = {}
    for v in variants:
        name = v.product.name if v.product else ""
        category = (
            v.product.category.name
            if v.product and v.product.category
            else ""
        )
        is_active = v.product.is_active if v.product else False
        g = grouped.setdefault(
            name, {"category": category, "is_active": is_active, "bundle": {}, "individual": []}
        )

        stock = v.stock
        if not stock:
            continue

        if stock.individual_count:
            g["individual"].append((v.sku or "-", stock.individual_count))

        for bs in stock.bundle_stocks or []:
            set_name = bs.set_type.name if bs.set_type else "Unknown"
            g["bundle"][set_name] = bs.bundle_count

    rows = []
    sl = 1
    for name, g in grouped.items():
        cat = g["category"]
        status_label = "Active" if g["is_active"] else "Inactive"
        for set_name, cnt in g["bundle"].items():
            rows.append({
                "Sl": sl,
                "Product": name,
                "Category": cat,
                "Status": status_label,
                "Stock Type": "Bundle",
                "Set Type / SKU": set_name,
                "Count": int(cnt or 0),
            })
            sl += 1
        for sku, cnt in g["individual"]:
            rows.append({
                "Sl": sl,
                "Product": name,
                "Category": cat,
                "Status": status_label,
                "Stock Type": "Individual",
                "Set Type / SKU": sku,
                "Count": int(cnt or 0),
            })
            sl += 1
        if not g["bundle"] and not g["individual"]:
            rows.append({
                "Sl": sl,
                "Product": name,
                "Category": cat,
                "Status": status_label,
                "Stock Type": "",
                "Set Type / SKU": "",
                "Count": 0,
            })
            sl += 1
    return rows


async def get_stock_summary(
    db: AsyncSession,
    tenant_id: Optional[uuid.UUID] = None,
    category_id: Optional[uuid.UUID] = None,
) -> dict:
    query = (
        select(ProductVariant)
        .where(ProductVariant.is_deleted == False)
        .options(
            selectinload(ProductVariant.product),
            selectinload(ProductVariant.stock).selectinload(Stock.bundle_stocks),
        )
        .join(ProductVariant.product)
        .where(Product.is_deleted == False)
    )
    if tenant_id:
        query = query.where(Product.tenant_id == tenant_id)
    if category_id:
        query = query.where(Product.category_id == category_id)

    result = await db.execute(query)
    variants = result.scalars().all()

    total_individual = sum(v.stock.individual_count for v in variants if v.stock)
    out_of_stock = sum(1 for v in variants if v.stock and v.stock.individual_count == 0)
    low_stock = sum(1 for v in variants if v.stock and 0 < v.stock.individual_count <= 10)
    total_variants = len(variants)

    return {
        "totalVariants": total_variants,
        "totalIndividualStock": total_individual,
        "outOfStock": out_of_stock,
        "lowStock": low_stock,
        "inStock": total_variants - out_of_stock - low_stock,
    }


async def get_low_stock_report_data(
    db: AsyncSession,
    threshold: int = 10,
    tenant_id: Optional[uuid.UUID] = None,
    category_id: Optional[uuid.UUID] = None,
) -> list[dict]:
    query = (
        select(ProductVariant)
        .where(ProductVariant.is_deleted == False)
        .options(
            selectinload(ProductVariant.product),
            selectinload(ProductVariant.stock),
        )
        .join(ProductVariant.product)
        .join(ProductVariant.stock)
        .where(Product.is_deleted == False, Stock.individual_count <= threshold)
    )

    if tenant_id:
        query = query.where(Product.tenant_id == tenant_id)
    if category_id:
        query = query.where(Product.category_id == category_id)

    result = await db.execute(query)
    variants = result.scalars().all()

    rows = []
    for v in variants:
        rows.append({
            "Product": v.product.name if v.product else "",
            "SKU": v.sku or "",
            "Size": v.size or "",
            "Color": v.color or "",
            "Individual Stock": v.stock.individual_count if v.stock else 0,
            "Alert": "OUT OF STOCK" if v.stock and v.stock.individual_count == 0 else "LOW STOCK",
        })
    return rows


# ── Product Report ─────────────────────────────────────────────────────────────

async def get_product_report_data(
    db: AsyncSession,
    tenant_id: Optional[uuid.UUID] = None,
    category_id: Optional[uuid.UUID] = None,
    is_active: Optional[bool] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> list[dict]:
    query = (
        select(Product)
        .where(Product.is_deleted == False)
        .options(
            selectinload(Product.model_ref),
            selectinload(Product.variants).selectinload(ProductVariant.stock),
        )
    )
    if tenant_id:
        query = query.where(Product.tenant_id == tenant_id)
    if category_id:
        query = query.where(Product.category_id == category_id)
    if is_active is not None:
        query = query.where(Product.is_active == is_active)

    products = (await db.execute(query)).scalars().all()
    if not products:
        return []

    product_ids = [p.id for p in products]

    bs_q = (
        select(
            ProductVariant.product_id.label("product_id"),
            SetType.name.label("set_type_name"),
            SetType.total_pieces.label("total_pieces"),
            func.coalesce(func.sum(BundleStock.bundle_count), 0).label("bundle_count"),
        )
        .join(Stock, Stock.variant_id == ProductVariant.id)
        .join(BundleStock, BundleStock.stock_id == Stock.id)
        .join(SetType, SetType.id == BundleStock.set_type_id)
        .where(ProductVariant.product_id.in_(product_ids))
        .where(ProductVariant.is_deleted == False)
        .group_by(ProductVariant.product_id, SetType.id, SetType.name, SetType.total_pieces)
        .order_by(SetType.name)
    )
    bs_rows = (await db.execute(bs_q)).all()

    # bundle_count from the DB is already PIECES (not number of boxes)
    bundle_map: dict[uuid.UUID, dict] = defaultdict(lambda: {"boxes": [], "box_pieces": 0})
    for r in bs_rows:
        cnt = int(r.bundle_count)  # pieces
        tp = int(r.total_pieces or 0)
        box_count = cnt // tp if tp else 0  # physical box count, derived
        bundle_map[r.product_id]["boxes"].append((r.set_type_name, tp, box_count))
        bundle_map[r.product_id]["box_pieces"] += cnt  # sum pieces directly

    status_q = (
        select(
            OrderItem.product_id.label("product_id"),
            Order.status.label("status"),
            func.coalesce(func.sum(OrderItem.count), 0).label("pieces"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .where(OrderItem.product_id.in_(product_ids))
        .group_by(OrderItem.product_id, Order.status)
    )
    on_q = (
        select(
            OrderItem.product_id.label("product_id"),
            func.array_agg(func.distinct(Order.order_number)).label("order_numbers"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .where(OrderItem.product_id.in_(product_ids))
        .group_by(OrderItem.product_id)
    )
    if date_from:
        df = datetime.combine(date_from, datetime.min.time())
        status_q = status_q.where(Order.created_at >= df)
        on_q = on_q.where(Order.created_at >= df)
    if date_to:
        dt = datetime.combine(date_to, datetime.max.time())
        status_q = status_q.where(Order.created_at <= dt)
        on_q = on_q.where(Order.created_at <= dt)

    status_map: dict[uuid.UUID, dict[str, int]] = defaultdict(dict)
    for r in (await db.execute(status_q)).all():
        sval = r.status.value if hasattr(r.status, "value") else str(r.status)
        status_map[r.product_id][sval] = int(r.pieces)

    order_num_map = {
        r.product_id: sorted(r.order_numbers or [])
        for r in (await db.execute(on_q)).all()
    }

    status_order = [s.value for s in OrderStatus]

    rows = []
    for p in products:
        active_variants = [v for v in p.variants if not v.is_deleted]
        stock_pcs = sum(v.stock.individual_count for v in active_variants if v.stock)

        binfo = bundle_map.get(p.id, {"boxes": [], "box_pieces": 0})
        # e.g. ["BOX-6(6) x0", "BOX-8(8) x9"]
        box_lines = [f"{name}({tp}) x{box_count}" for name, tp, box_count in binfo["boxes"]]

        order_nums = order_num_map.get(p.id, [])
        pstatus = status_map.get(p.id, {})
        total_pieces_ordered = sum(pstatus.values())

        product_cols = {
            "Product": p.name,
            "Model": p.model_ref.name if p.model_ref else "",
            "Sell Type": p.sell_type.value,
            "DP Price": float(p.dp_price),
            "MRP(Net of Tax)": float(p.mrp),
            "Stock (pcs)": stock_pcs,
            "Stock Boxes (pcs)": binfo["box_pieces"],
            **{sval: pstatus.get(sval, 0) for sval in status_order},
            "Total Ordered (pcs)": total_pieces_ordered,
            "Status": "Active" if p.is_active else "Inactive",
        }

        n_rows = max(len(box_lines), len(order_nums), 1)
        for i in range(n_rows):
            rows.append({
                **product_cols,
                "Box SL": i + 1 if i < len(box_lines) else "",
                "Stock Boxes": box_lines[i] if i < len(box_lines) else "",
                "Order SL": i + 1 if i < len(order_nums) else "",
                "Order Numbers": order_nums[i] if i < len(order_nums) else "",
            })

    return rows

# ── Shop Report ────────────────────────────────────────────────────────────────

async def get_shop_report_data(
    db: AsyncSession,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    tenant_id: Optional[uuid.UUID] = None,
    state_id: Optional[uuid.UUID] = None,
    district_id: Optional[uuid.UUID] = None,
    taluk_id: Optional[uuid.UUID] = None,
    is_ebo: Optional[bool] = None,
) -> list[dict]:
    query = (
        select(Shop)
        .where(Shop.is_deleted == False)
        .options(
            selectinload(Shop.district).selectinload(District.state),
            selectinload(Shop.taluk),
        )
    )

    if district_id:
        query = query.where(Shop.district_id == district_id)
    if taluk_id:
        query = query.where(Shop.taluk_id == taluk_id)
    if is_ebo is not None:
        query = query.where(Shop.is_ebo == is_ebo)
    if state_id:
        query = query.join(Shop.district).where(District.state_id == state_id)

    result = await db.execute(query)
    shops = result.scalars().unique().all()

    rows = []
    for s in shops:
        order_q = (
            select(func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0))
            .where(
                Order.shop_id == s.id,
                Order.is_deleted == False,
                Order.parent_order_id == None,  # noqa
            )
        )
        order_q = _date_filters(order_q, Order, date_from, date_to)
        count, value = (await db.execute(order_q)).one()

        last_order_q = await db.execute(
            select(func.max(Order.created_at)).where(
                Order.shop_id == s.id,
                Order.is_deleted == False,
            )
        )
        last_order_at = last_order_q.scalar()

        rows.append({
            "Shop": s.name,
            "Contact Person": s.contact_person or "",
            "Phone": s.contact_number or "",
            "District": s.district.name if s.district else "",
            "State": s.district.state.name if s.district and s.district.state else "",
            "Taluk": s.taluk.name if s.taluk else "",
            "EBO": "Yes" if s.is_ebo else "No",
            "Active": "Yes" if s.is_active else "No",
            "Total Orders": count,
            "Total Value (₹)": float(value),
            "Last Order Date": last_order_at.strftime("%Y-%m-%d") if last_order_at else "",
        })
    return rows


async def get_shop_summary(
    db: AsyncSession,
    state_id: Optional[uuid.UUID] = None,
    district_id: Optional[uuid.UUID] = None,
) -> dict:
    base_query = select(func.count(Shop.id)).where(Shop.is_deleted == False)

    if district_id:
        base_query = base_query.where(Shop.district_id == district_id)
    if state_id:
        base_query = base_query.join(Shop.district).where(District.state_id == state_id)

    total = (await db.execute(base_query)).scalar() or 0

    ebo_query = base_query.where(Shop.is_ebo == True)  # noqa
    ebo = (await db.execute(ebo_query)).scalar() or 0

    active_query = base_query.where(Shop.is_active == True)  # noqa
    active = (await db.execute(active_query)).scalar() or 0

    return {
        "totalShops": total,
        "eboShops": ebo,
        "activeShops": active,
        "inactiveShops": total - active,
    }


# ── User Report ────────────────────────────────────────────────────────────────

async def get_user_report_data(
    db: AsyncSession,
    role_id: Optional[uuid.UUID] = None,
    tenant_id: Optional[uuid.UUID] = None,
    district_id: Optional[uuid.UUID] = None,
    state_id: Optional[uuid.UUID] = None,
    is_active: Optional[bool] = None,
) -> list[dict]:
    query = (
        select(User)
        .where(User.is_deleted == False)
        .options(
            selectinload(User.role),
            selectinload(User.user_districts)
            .selectinload(UserDistrict.district)
            .selectinload(District.state),
            selectinload(User.user_tenants),
        )
    )

    if role_id:
        query = query.where(User.role_id == role_id)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if tenant_id:
        query = query.where(User.user_tenants.any(UserTenant.tenant_id == tenant_id))
    if district_id:
        query = query.where(User.user_districts.any(UserDistrict.district_id == district_id))
    if state_id:
        query = query.where(
            User.user_districts.any(
                UserDistrict.district_id.in_(
                    select(District.id).where(District.state_id == state_id)
                )
            )
        )

    result = await db.execute(query)
    users = result.scalars().unique().all()

    rows = []
    for u in users:
        districts = ", ".join([ud.district.name for ud in u.user_districts if ud.district])
        states = ", ".join(list(set([
            ud.district.state.name
            for ud in u.user_districts
            if ud.district and ud.district.state
        ])))
        rows.append({
            "Username": u.username,
            "First Name": u.first_name,
            "Last Name": u.last_name or "",
            "Email": u.email,
            "Phone": u.phone or "",
            "Role": u.role.name if u.role else "",
            "Districts": districts,
            "States": states,
            "Active": "Yes" if u.is_active else "No",
            "Verified": "Yes" if u.is_verified else "No",
            "Created": u.created_at.strftime("%Y-%m-%d"),
        })
    return rows


# ── Executive Performance Report ───────────────────────────────────────────────

async def get_executive_performance_data(
    db: AsyncSession,
    year: int,
    month: int,
    tenant_id: Optional[uuid.UUID] = None,
    district_id: Optional[uuid.UUID] = None,
    state_id: Optional[uuid.UUID] = None,
) -> list[dict]:
    # Month window as a half-open range (index-friendly, no extract()).
    period_start = datetime(year, month, 1)
    period_end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)

    excluded = [OrderStatus.rejected, OrderStatus.returned, OrderStatus.cancelled]
    status_columns = [s for s in OrderStatus if s not in excluded]  # stable column set

    # ---- executives ----
    exec_query = (
        select(User)
        .join(User.role)
        .where(
            User.is_deleted == False,
            User.is_active == True,
            Role.name == "executive",
        )
        .options(
            selectinload(User.user_districts)
            .selectinload(UserDistrict.district)
            .selectinload(District.state),
        )
    )

    if tenant_id:
        # NOTE: confirm the junction names match your schema (UserTenant / user_tenants)
        exec_query = exec_query.where(
            User.user_tenants.any(UserTenant.tenant_id == tenant_id)
        )
    if district_id:
        exec_query = exec_query.where(
            User.user_districts.any(UserDistrict.district_id == district_id)
        )
    if state_id:
        exec_query = exec_query.where(
            User.user_districts.any(
                UserDistrict.district_id.in_(
                    select(District.id).where(District.state_id == state_id)
                )
            )
        )

    executives = (await db.execute(exec_query)).scalars().unique().all()
    if not executives:
        return []

    exec_ids = [e.id for e in executives]

    # ---- one grouped query for all order aggregates ----
    order_filters = [
        Order.assigned_executive.in_(exec_ids),
        Order.is_deleted == False,
        Order.status.not_in(excluded),
        Order.parent_order_id == None,  # noqa
        Order.created_at >= period_start,
        Order.created_at < period_end,
    ]
    if tenant_id:
        order_filters.append(Order.tenant_id == tenant_id)  # confirm column name

    agg_rows = (await db.execute(
        select(
            Order.assigned_executive,
            Order.status,
            func.count(Order.id),
            func.coalesce(func.sum(Order.total_amount), 0),
        )
        .where(*order_filters)
        .group_by(Order.assigned_executive, Order.status)
    )).all()

    by_exec: dict[uuid.UUID, dict] = defaultdict(dict)
    for exec_id, status, cnt, value in agg_rows:
        by_exec[exec_id][status] = (cnt, float(value))

    # ---- one query for all targets ----
    target_rows = (await db.execute(
        select(ExecutiveTarget).where(
            ExecutiveTarget.user_id.in_(exec_ids),
            ExecutiveTarget.year == year,
            ExecutiveTarget.month == month,
        )
    )).scalars().all()

    targets_by_exec: dict[uuid.UUID, dict] = defaultdict(dict)
    for t in target_rows:
        targets_by_exec[t.user_id][t.target_type] = float(t.target_value)

    # ---- build rows ----
    rows = []
    for exe in executives:
        per_status = by_exec.get(exe.id, {})
        status_counts = {s: per_status.get(s, (0, 0.0))[0] for s in status_columns}

        order_count = sum(status_counts.values())
        order_value = sum(v for _, v in per_status.values())
        delivered_count = status_counts.get(OrderStatus.delivered, 0)

        tmap = targets_by_exec.get(exe.id, {})
        count_target = tmap.get(TargetType.order_count, 0)
        value_target = tmap.get(TargetType.order_value, 0)

        districts = ", ".join(
            ud.district.name for ud in exe.user_districts if ud.district
        )

        rows.append({
            "Executive": f"{exe.first_name} {exe.last_name}".strip(),
            "Username": exe.username,
            "Phone": exe.phone or "",
            "Districts": districts,
            "Total Orders": order_count,
            "Delivered Orders": delivered_count,
            "Delivery Rate %": round(delivered_count / order_count * 100, 2) if order_count else 0,
            "Order Count Target": count_target,
            "Count Achievement %": round(order_count / count_target * 100, 2) if count_target else "N/A",
            "Order Value (₹)": order_value,
            "Value Target (₹)": value_target,
            "Value Achievement %": round(order_value / value_target * 100, 2) if value_target else "N/A",
            **{f"Status - {s.value}": status_counts[s] for s in status_columns},
        })

    return rows


async def get_executive_summary(
    db: AsyncSession,
    year: int,
    month: int,
    tenant_id: Optional[uuid.UUID] = None,
) -> dict:
    exec_count = (await db.execute(
        select(func.count(User.id))
        .where(User.is_deleted == False, User.is_active == True)
        .join(User.role)
        .where(Role.name == "executive")
    )).scalar() or 0

    excluded = [OrderStatus.rejected, OrderStatus.returned, OrderStatus.cancelled]

    total_orders = (await db.execute(
        select(func.count(Order.id)).where(
            Order.is_deleted == False,
            Order.status.not_in(excluded),
            Order.parent_order_id == None,  # noqa
            extract("year", Order.created_at) == year,
            extract("month", Order.created_at) == month,
        )
    )).scalar() or 0

    total_value = float((await db.execute(
        select(func.coalesce(func.sum(Order.total_amount), 0)).where(
            Order.is_deleted == False,
            Order.status.not_in(excluded),
            Order.parent_order_id == None,  # noqa
            extract("year", Order.created_at) == year,
            extract("month", Order.created_at) == month,
        )
    )).scalar() or 0)

    return {
        "year": year,
        "month": month,
        "totalExecutives": exec_count,
        "totalOrders": total_orders,
        "totalOrderValue": total_value,
        "averageOrdersPerExecutive": round(total_orders / exec_count, 2) if exec_count else 0,
        "averageValuePerExecutive": round(total_value / exec_count, 2) if exec_count else 0,
    }


# ── Distributor Report ─────────────────────────────────────────────────────────

async def get_distributor_report_data(
    db: AsyncSession,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    tenant_id: Optional[uuid.UUID] = None,
    district_id: Optional[uuid.UUID] = None,
    state_id: Optional[uuid.UUID] = None,
) -> list[dict]:
    dist_query = (
        select(User)
        .where(User.is_deleted == False)
        .join(User.role)
        .where(Role.name == "distributor")
        .options(
            selectinload(User.user_districts).selectinload(UserDistrict.district),
        )
    )

    if district_id:
        dist_query = dist_query.where(
            User.user_districts.any(UserDistrict.district_id == district_id)
        )

    dist_result = await db.execute(dist_query)
    distributors = dist_result.scalars().unique().all()

    rows = []
    for d in distributors:
        base = [
            Order.distributor_id == d.id,
            Order.is_deleted == False,
            Order.parent_order_id == None,  # noqa
        ]
        if date_from:
            base.append(Order.created_at >= datetime.combine(date_from, datetime.min.time()))
        if date_to:
            base.append(Order.created_at <= datetime.combine(date_to, datetime.max.time()))

        count, value = (await db.execute(
            select(func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0)).where(*base)
        )).one()

        delivered = (await db.execute(
            select(func.count(Order.id)).where(*base, Order.status == OrderStatus.delivered)
        )).scalar() or 0

        rejected = (await db.execute(
            select(func.count(Order.id)).where(*base, Order.status == OrderStatus.rejected)
        )).scalar() or 0

        districts = ", ".join([ud.district.name for ud in d.user_districts if ud.district])

        rows.append({
            "Distributor": f"{d.first_name} {d.last_name}".strip(),
            "Username": d.username,
            "Phone": d.phone or "",
            "Districts": districts,
            "Total Orders": count,
            "Delivered": delivered,
            "Rejected": rejected,
            "Total Value (₹)": float(value),
            "Delivery Rate %": round((delivered / count * 100), 2) if count else 0,
        })

    return rows


# ── Returns Report ─────────────────────────────────────────────────────────────

async def get_returns_report_data(
    db: AsyncSession,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    tenant_id: Optional[uuid.UUID] = None,
    product_id: Optional[uuid.UUID] = None,
) -> list[dict]:
    query = (
        select(OrderReturn)
        .options(
            selectinload(OrderReturn.order),
            selectinload(OrderReturn.product),
            selectinload(OrderReturn.variant),
            selectinload(OrderReturn.set_type),
            selectinload(OrderReturn.processor),
        )
    )

    if date_from:
        query = query.where(OrderReturn.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        query = query.where(OrderReturn.created_at <= datetime.combine(date_to, datetime.max.time()))
    if product_id:
        query = query.where(OrderReturn.product_id == product_id)

    result = await db.execute(query.order_by(OrderReturn.created_at.desc()))
    returns = result.scalars().all()

    rows = []
    for r in returns:
        rows.append({
            "Date": r.created_at.strftime("%Y-%m-%d"),
            "Order Number": r.order.order_number if r.order else "",
            "Product": r.product.name if r.product else "",
            "Variant Size": r.variant.size if r.variant else "",
            "Variant Color": r.variant.color if r.variant else "",
            "Set Type": r.set_type.name if r.set_type else "",
            "Return Type": r.return_type.value,
            "Count": r.count,
            "Processed By": f"{r.processor.first_name} {r.processor.last_name}".strip() if r.processor else "",
            "Notes": r.notes or "",
        })
    return rows


async def get_executive_sales_summary(
    db: AsyncSession,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    tenant_id: Optional[uuid.UUID] = None,
) -> list[dict]:
    excluded = [OrderStatus.rejected, OrderStatus.returned, OrderStatus.cancelled]

    filters = [
        Order.is_deleted == False,
        Order.parent_order_id == None,  # noqa
        Order.status.not_in(excluded),
    ]
    if tenant_id:
        filters.append(Order.tenant_id == tenant_id)
    if date_from:
        filters.append(Order.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        filters.append(Order.created_at <= datetime.combine(date_to, datetime.max.time()))

    # pieces from item join
    pieces_q = (
        select(
            Order.assigned_executive.label("exec_id"),
            func.coalesce(func.sum(OrderItem.count), 0).label("pieces"),
        )
        .join(OrderItem, OrderItem.order_id == Order.id)
        .where(*filters)
        .group_by(Order.assigned_executive)
    )

    # order count + true order value (NO item join -> no fan-out)
    orders_q = (
        select(
            Order.assigned_executive.label("exec_id"),
            func.count(Order.id).label("order_count"),
            func.coalesce(func.sum(Order.total_amount), 0).label("order_value"),
        )
        .where(*filters)
        .group_by(Order.assigned_executive)
    )

    pieces_map = {r.exec_id: int(r.pieces) for r in (await db.execute(pieces_q)).all()}
    orders_map = {
        r.exec_id: (int(r.order_count), float(r.order_value))
        for r in (await db.execute(orders_q)).all()
    }

    exec_ids = [eid for eid in orders_map if eid is not None]
    execs: dict[uuid.UUID, User] = {}
    if exec_ids:
        eq = (
            select(User)
            .where(User.id.in_(exec_ids))
            .options(selectinload(User.user_districts).selectinload(UserDistrict.district))
        )
        execs = {u.id: u for u in (await db.execute(eq)).scalars().unique().all()}

    rows = []
    for eid, (order_count, order_value) in sorted(
        orders_map.items(), key=lambda x: x[1][1], reverse=True
    ):
        if eid is None:
            name, districts = "(Unassigned)", ""
        else:
            u = execs.get(eid)
            name = f"{u.first_name} {u.last_name}".strip() if u else str(eid)
            districts = ", ".join(ud.district.name for ud in u.user_districts if ud.district) if u else ""

        rows.append({
            "Executive": name,
            "Districts": districts,
            "Orders": order_count,
            "Total Pieces": pieces_map.get(eid, 0),
            "Total Value (₹)": round(order_value, 2),
        })
    return rows


async def get_district_category_report(
    db: AsyncSession,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    tenant_id: Optional[uuid.UUID] = None,
) -> list[dict]:
    excluded = [OrderStatus.rejected, OrderStatus.returned, OrderStatus.cancelled]

    filters = [
        Order.is_deleted == False,
        Order.parent_order_id == None,  # noqa
        Order.status.not_in(excluded),
    ]
    if tenant_id:
        filters.append(Order.tenant_id == tenant_id)
    if date_from:
        filters.append(Order.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        filters.append(Order.created_at <= datetime.combine(date_to, datetime.max.time()))

    q = (
        select(
            District.name.label("district"),
            Category.name.label("category"),
            func.count(func.distinct(Product.id)).label("distinct_products"),
            func.coalesce(func.sum(OrderItem.count), 0).label("pieces"),
            func.coalesce(func.sum(OrderItem.total_price), 0).label("value"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .join(Product, OrderItem.product_id == Product.id)
        .join(Category, Product.category_id == Category.id)
        .join(Shop, Order.shop_id == Shop.id)
        .join(District, Shop.district_id == District.id)
        .where(*filters)
        .group_by(District.name, Category.name)
        .order_by(District.name, Category.name)
    )

    rows = []
    for r in (await db.execute(q)).all():
        rows.append({
            "District": r.district,
            "Category": r.category,
            "Distinct Products": int(r.distinct_products),
            "Pieces Purchased": int(r.pieces),
            "Value (₹)": round(float(r.value), 2),
        })
    return rows