import uuid
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
import io

from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.order import OrderStatus, OrderType
from app.services import report_data as rd
from app.services.report_data import (
    get_order_consolidation_report,
    get_executive_wise_report,
    _build_consolidation_excel,
    _build_executive_wise_excel,
)
from app.services.report_export import generate_excel, generate_pdf
from app.schemas.common import CommonResponse, ResponseModel

router = APIRouter(prefix="/reports", tags=["Reports"])


# ── Helpers ────────────────────────────────────────────────────────────────────

def excel_response(data: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}.xlsx"},
    )


def pdf_response(data: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}.pdf"},
    )


def _now_str() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ══════════════════════════════════════════════════════════════════════════════
# CONSOLIDATION REPORTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/consolidation/summary", response_model=CommonResponse)
async def consolidation_summary(
    tenant_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    JSON summary of order consolidation report.

    Channel Intimates: ?tenantId=<intimates-uuid>
    Channel Fashion:   ?tenantId=<fashion-uuid>
    All tenants:       no tenantId param
    """
    data = await get_order_consolidation_report(
        db,
        tenant_id=tenant_id,
        date_from=date_from,
        date_to=date_to,
    )
    return ResponseModel(data=data, message="Consolidation report fetched")


@router.get("/consolidation/excel")
async def consolidation_excel(
    tenant_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    title: str = Query(default="ORDER CONSOLIDATION"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Download consolidation Excel report.

    Channel Intimates: ?tenantId=<intimates-uuid>&title=ESSENTIAL ORDER CONSOLIDATION
    Channel Fashion:   ?tenantId=<fashion-uuid>&title=FASHION ORDER CONSOLIDATION
    """
    report = await get_order_consolidation_report(
        db,
        tenant_id=tenant_id,
        date_from=date_from,
        date_to=date_to,
    )
    data = _build_consolidation_excel(report, title)
    return excel_response(data, f"consolidation_{_now_str()}")


# ══════════════════════════════════════════════════════════════════════════════
# EXECUTIVE WISE REPORTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/executive-wise/summary", response_model=CommonResponse)
async def executive_wise_summary(
    tenant_id: uuid.UUID | None = None,
    year: int | None = None,
    month: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    JSON summary of executive wise report.

    Channel Intimates: ?tenantId=<intimates-uuid>&year=2026&month=4
    Channel Fashion:   ?tenantId=<fashion-uuid>&year=2026&month=4
    """
    now = datetime.utcnow()
    data = await get_executive_wise_report(
        db,
        year=year or now.year,
        month=month or now.month,
        tenant_id=tenant_id,
        date_from=date_from,
        date_to=date_to,
    )
    return ResponseModel(data=data, message="Executive wise report fetched")


@router.get("/executive-wise/excel")
async def executive_wise_excel(
    tenant_id: uuid.UUID | None = None,
    year: int | None = None,
    month: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    title: str = Query(default="ORDER STATISTICS"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Download executive wise Excel report.

    Channel Intimates: ?tenantId=<intimates-uuid>&title=ESSENTIALS NORMAL ORDER STATISTICS
    Channel Fashion:   ?tenantId=<fashion-uuid>&title=FASHION ORDER STATISTICS
    """
    now = datetime.utcnow()
    report = await get_executive_wise_report(
        db,
        year=year or now.year,
        month=month or now.month,
        tenant_id=tenant_id,
        date_from=date_from,
        date_to=date_to,
    )
    data = _build_executive_wise_excel(report, title)
    return excel_response(data, f"executive_wise_{_now_str()}")


# ══════════════════════════════════════════════════════════════════════════════
# ORDER REPORTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/orders/summary", response_model=CommonResponse)
async def order_summary(
    tenant_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Order counts and values grouped by status, type, price type."""
    data = await rd.get_order_summary(
        db,
        tenant_id=tenant_id,
        date_from=date_from,
        date_to=date_to,
    )
    return ResponseModel(data=data, message="Order summary fetched")


@router.get("/orders/excel")
async def orders_excel(
    date_from: date | None = None,
    date_to: date | None = None,
    tenant_id: uuid.UUID | None = None,
    state_id: uuid.UUID | None = None,
    district_id: uuid.UUID | None = None,
    taluk_id: uuid.UUID | None = None,
    shop_id: uuid.UUID | None = None,
    distributor_id: uuid.UUID | None = None,
    assigned_executive: uuid.UUID | None = None,
    status: OrderStatus | None = None,
    order_type: OrderType | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download detailed order line items as Excel."""
    rows = await rd.get_order_report_data(
        db,
        date_from=date_from,
        date_to=date_to,
        tenant_id=tenant_id,
        state_id=state_id,
        district_id=district_id,
        taluk_id=taluk_id,
        shop_id=shop_id,
        distributor_id=distributor_id,
        assigned_executive=assigned_executive,
        status=status,
        order_type=order_type,
    )
    return excel_response(
        generate_excel(
            rows,
            "Orders",
            merge_key="Order Number",
            merge_cols=(
                "Order Number",
                "Bill Number",
                "Type",
                "Price Type",
                "Shipment Status",
                "Tenant",
                "Shop",
                "District",
                "Taluk",
                "Executive",
                "Distributor",
                "Order Subtotal",
                "Order Discount",
                "Order Total",
                "Transporter Name",
                "Tracking Number",
                "Boxes Dispatched",
                "Delivery Notes",
                "Booking Date",
                "Dispatched At",
                "Delivered At",
                "Delivery Date",
                "TAT (days)",
                ),
        ),
        f"orders_{_now_str()}",
    )


@router.get("/orders/pdf")
async def orders_pdf(
    date_from: date | None = None,
    date_to: date | None = None,
    tenant_id: uuid.UUID | None = None,
    state_id: uuid.UUID | None = None,
    district_id: uuid.UUID | None = None,
    taluk_id: uuid.UUID | None = None,
    shop_id: uuid.UUID | None = None,
    distributor_id: uuid.UUID | None = None,
    assigned_executive: uuid.UUID | None = None,
    status: OrderStatus | None = None,
    order_type: OrderType | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download detailed order report as PDF."""
    rows = await rd.get_order_report_data(
        db,
        date_from=date_from,
        date_to=date_to,
        tenant_id=tenant_id,
        state_id=state_id,
        district_id=district_id,
        taluk_id=taluk_id,
        shop_id=shop_id,
        distributor_id=distributor_id,
        assigned_executive=assigned_executive,
        status=status,
        order_type=order_type,
    )
    ORDER_COL_WEIGHTS = {
        "Order Number": 1.5, "Date": 1, "Type": 0.8, "Price Type": 0.6,
        "Status": 1, "Tenant": 1.0, "Shop": 1.7, "District": 1.2, "Taluk": 1.2,
        "Executive": 1.5, "Distributor": 1.5, "Products": 2,
        "Total Items": 0.55, "Total Amount": 0.8, "Placed At": 1, "Delivered At": 1,
    }

    # in orders_pdf:
    return pdf_response(
        generate_pdf(rows, "Orders Report", col_weights=ORDER_COL_WEIGHTS),
        f"orders_{_now_str()}",
    )

# ══════════════════════════════════════════════════════════════════════════════
# STOCK REPORTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/stock/summary", response_model=CommonResponse)
async def stock_summary(
    tenant_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stock overview — total, out of stock, low stock counts."""
    data = await rd.get_stock_summary(
        db,
        tenant_id=tenant_id,
        category_id=category_id,
    )
    return ResponseModel(data=data, message="Stock summary fetched")


@router.get("/stock/excel")
async def stock_excel(
    tenant_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download stock levels per variant as Excel."""
    rows = await rd.get_stock_report_data(
        db,
        tenant_id=tenant_id,
        category_id=category_id,
        product_id=product_id,
    )
    return excel_response(
        generate_excel(
            rows, "Stock", merge_key="Product", merge_cols=("Sl", "Product", "Category", "Stock Type")),
        f"stock_{_now_str()}")


@router.get("/stock/pdf")
async def stock_pdf(
    tenant_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download stock levels as PDF."""
    rows = await rd.get_stock_report_data(
        db,
        tenant_id=tenant_id,
        category_id=category_id,
        product_id=product_id,
    )
    return pdf_response(generate_pdf(rows, "Stock Report"), f"stock_{_now_str()}")


@router.get("/stock/low-stock/excel")
async def low_stock_excel(
    threshold: int = Query(default=10, description="Stock count threshold"),
    tenant_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download low stock / out of stock variants as Excel."""
    rows = await rd.get_low_stock_report_data(
        db,
        threshold=threshold,
        tenant_id=tenant_id,
        category_id=category_id,
    )
    return excel_response(generate_excel(rows, "Low Stock"), f"low_stock_{_now_str()}")


@router.get("/stock/low-stock/pdf")
async def low_stock_pdf(
    threshold: int = Query(default=10),
    tenant_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download low stock report as PDF."""
    rows = await rd.get_low_stock_report_data(
        db,
        threshold=threshold,
        tenant_id=tenant_id,
        category_id=category_id,
    )
    return pdf_response(generate_pdf(rows, "Low Stock Report"), f"low_stock_{_now_str()}")


# ══════════════════════════════════════════════════════════════════════════════
# PRODUCT REPORTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/products/excel")
async def products_excel(
    tenant_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download product report with stock and order stats as Excel."""
    rows = await rd.get_product_report_data(
        db,
        tenant_id=tenant_id,
        category_id=category_id,
        is_active=is_active,
        date_from=date_from,
        date_to=date_to,
    )
    return excel_response(
        generate_excel(
            rows,
            "Products",
            merge_key="Product",
            merge_cols=(
                "Product", "Model", "Sell Type", "DP Price", "MRP(Net of Tax)",
                "Stock (pcs)", "Stock Boxes (pcs)",
                *[s.value for s in OrderStatus],
                "Total Ordered (pcs)", "Status",
            ),
        ),
        f"products_{_now_str()}",
    )


@router.get("/products/pdf")
async def products_pdf(
    tenant_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download product report as PDF."""
    rows = await rd.get_product_report_data(
        db,
        tenant_id=tenant_id,
        category_id=category_id,
        is_active=is_active,
        date_from=date_from,
        date_to=date_to,
    )
    return pdf_response(generate_pdf(rows, "Products Report"), f"products_{_now_str()}")


# ══════════════════════════════════════════════════════════════════════════════
# USER REPORTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/users/excel")
async def users_excel(
    role_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    district_id: uuid.UUID | None = None,
    state_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download users report with role, district, state info as Excel."""
    rows = await rd.get_user_report_data(
        db,
        role_id=role_id,
        tenant_id=tenant_id,
        district_id=district_id,
        state_id=state_id,
        is_active=is_active,
    )
    return excel_response(generate_excel(rows, "Users"), f"users_{_now_str()}")


@router.get("/users/pdf")
async def users_pdf(
    role_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    district_id: uuid.UUID | None = None,
    state_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download users report as PDF."""
    rows = await rd.get_user_report_data(
        db,
        role_id=role_id,
        tenant_id=tenant_id,
        district_id=district_id,
        state_id=state_id,
        is_active=is_active,
    )
    return pdf_response(generate_pdf(rows, "Users Report"), f"users_{_now_str()}")


# ══════════════════════════════════════════════════════════════════════════════
# EXECUTIVE PERFORMANCE REPORTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/executives/summary", response_model=CommonResponse)
async def executive_summary(
    year: int | None = None,
    month: int | None = None,
    tenant_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Overall executive performance summary for a month."""
    now = datetime.utcnow()
    data = await rd.get_executive_summary(
        db,
        year=year or now.year,
        month=month or now.month,
        tenant_id=tenant_id,
    )
    return ResponseModel(data=data, message="Executive summary fetched")


@router.get("/executives/excel")
async def executive_performance_excel(
    year: int | None = None,
    month: int | None = None,
    tenant_id: uuid.UUID | None = None,
    district_id: uuid.UUID | None = None,
    state_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download executive performance vs targets as Excel."""
    now = datetime.utcnow()
    rows = await rd.get_executive_performance_data(
        db,
        year=year or now.year,
        month=month or now.month,
        tenant_id=tenant_id,
        district_id=district_id,
        state_id=state_id,
    )
    return excel_response(
        generate_excel(rows, "Executive Performance"),
        f"executive_performance_{_now_str()}"
    )


@router.get("/executives/pdf")
async def executive_performance_pdf(
    year: int | None = None,
    month: int | None = None,
    tenant_id: uuid.UUID | None = None,
    district_id: uuid.UUID | None = None,
    state_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download executive performance report as PDF."""
    now = datetime.utcnow()
    rows = await rd.get_executive_performance_data(
        db,
        year=year or now.year,
        month=month or now.month,
        tenant_id=tenant_id,
        district_id=district_id,
        state_id=state_id,
    )
    return pdf_response(
        generate_pdf(rows, "Executive Performance Report"),
        f"executive_performance_{_now_str()}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# DISTRIBUTOR REPORTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/distributors/excel")
async def distributors_excel(
    date_from: date | None = None,
    date_to: date | None = None,
    tenant_id: uuid.UUID | None = None,
    district_id: uuid.UUID | None = None,
    state_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download distributor order summary as Excel."""
    rows = await rd.get_distributor_report_data(
        db,
        date_from=date_from,
        date_to=date_to,
        tenant_id=tenant_id,
        district_id=district_id,
        state_id=state_id,
    )
    return excel_response(generate_excel(rows, "Distributors"), f"distributors_{_now_str()}")


@router.get("/distributors/pdf")
async def distributors_pdf(
    date_from: date | None = None,
    date_to: date | None = None,
    tenant_id: uuid.UUID | None = None,
    district_id: uuid.UUID | None = None,
    state_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download distributor report as PDF."""
    rows = await rd.get_distributor_report_data(
        db,
        date_from=date_from,
        date_to=date_to,
        tenant_id=tenant_id,
        district_id=district_id,
        state_id=state_id,
    )
    return pdf_response(generate_pdf(rows, "Distributor Report"), f"distributors_{_now_str()}")


# ══════════════════════════════════════════════════════════════════════════════
# SHOP REPORTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/shops/summary", response_model=CommonResponse)
async def shop_summary(
    state_id: uuid.UUID | None = None,
    district_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Shop counts — total, EBO, active, inactive."""
    data = await rd.get_shop_summary(
        db,
        state_id=state_id,
        district_id=district_id,
    )
    return ResponseModel(data=data, message="Shop summary fetched")


@router.get("/shops/excel")
async def shops_excel(
    date_from: date | None = None,
    date_to: date | None = None,
    tenant_id: uuid.UUID | None = None,
    state_id: uuid.UUID | None = None,
    district_id: uuid.UUID | None = None,
    taluk_id: uuid.UUID | None = None,
    is_ebo: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download shop report with order history as Excel."""
    rows = await rd.get_shop_report_data(
        db,
        date_from=date_from,
        date_to=date_to,
        tenant_id=tenant_id,
        state_id=state_id,
        district_id=district_id,
        taluk_id=taluk_id,
        is_ebo=is_ebo,
    )
    return excel_response(generate_excel(rows, "Shops"), f"shops_{_now_str()}")


@router.get("/shops/pdf")
async def shops_pdf(
    date_from: date | None = None,
    date_to: date | None = None,
    tenant_id: uuid.UUID | None = None,
    state_id: uuid.UUID | None = None,
    district_id: uuid.UUID | None = None,
    taluk_id: uuid.UUID | None = None,
    is_ebo: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download shop report as PDF."""
    rows = await rd.get_shop_report_data(
        db,
        date_from=date_from,
        date_to=date_to,
        tenant_id=tenant_id,
        state_id=state_id,
        district_id=district_id,
        taluk_id=taluk_id,
        is_ebo=is_ebo,
    )
    return pdf_response(generate_pdf(rows, "Shop Report"), f"shops_{_now_str()}")


# ══════════════════════════════════════════════════════════════════════════════
# RETURNS REPORTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/returns/excel")
async def returns_excel(
    date_from: date | None = None,
    date_to: date | None = None,
    tenant_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download returns report as Excel."""
    rows = await rd.get_returns_report_data(
        db,
        date_from=date_from,
        date_to=date_to,
        tenant_id=tenant_id,
        product_id=product_id,
    )
    return excel_response(generate_excel(rows, "Returns"), f"returns_{_now_str()}")


@router.get("/returns/pdf")
async def returns_pdf(
    date_from: date | None = None,
    date_to: date | None = None,
    tenant_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download returns report as PDF."""
    rows = await rd.get_returns_report_data(
        db,
        date_from=date_from,
        date_to=date_to,
        tenant_id=tenant_id,
        product_id=product_id,
    )
    return pdf_response(generate_pdf(rows, "Returns Report"), f"returns_{_now_str()}")


@router.get("/executives/sales/excel")
async def executive_sales_excel(
    tenant_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = await rd.get_executive_sales_summary(db, date_from=date_from, date_to=date_to, tenant_id=tenant_id)
    return excel_response(generate_excel(rows, "Executive Sales"), f"executive_sales_{_now_str()}")


@router.get("/districts/categories/excel")
async def district_category_excel(
    tenant_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = await rd.get_district_category_report(db, date_from=date_from, date_to=date_to, tenant_id=tenant_id)
    return excel_response(generate_excel(rows, "District Categories"), f"district_categories_{_now_str()}")