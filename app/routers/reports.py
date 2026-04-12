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
from app.services.report_export import generate_excel, generate_pdf
from app.schemas.common import CommonResponse, ResponseModel

router = APIRouter(prefix="/reports", tags=["Reports"])


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


# ── Order Summary (JSON) ───────────────────────────────────────────────────────

@router.get("/orders/summary", response_model=CommonResponse)
async def order_summary(
    tenant_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await rd.get_order_summary(db, tenant_id=tenant_id, date_from=date_from, date_to=date_to)
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
    rows = await rd.get_order_report_data(
        db, date_from=date_from, date_to=date_to,
        tenant_id=tenant_id, state_id=state_id,
        district_id=district_id, taluk_id=taluk_id,
        shop_id=shop_id, distributor_id=distributor_id,
        assigned_executive=assigned_executive,
        status=status, order_type=order_type,
    )
    return excel_response(generate_excel(rows, "Orders"), f"orders_{_now_str()}")


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
    rows = await rd.get_order_report_data(
        db, date_from=date_from, date_to=date_to,
        tenant_id=tenant_id, state_id=state_id,
        district_id=district_id, taluk_id=taluk_id,
        shop_id=shop_id, distributor_id=distributor_id,
        assigned_executive=assigned_executive,
        status=status, order_type=order_type,
    )
    return pdf_response(generate_pdf(rows, "Orders Report"), f"orders_{_now_str()}")


# ── Stock ──────────────────────────────────────────────────────────────────────

@router.get("/stock/summary", response_model=CommonResponse)
async def stock_summary(
    tenant_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await rd.get_stock_summary(db, tenant_id=tenant_id, category_id=category_id)
    return ResponseModel(data=data, message="Stock summary fetched")


@router.get("/stock/excel")
async def stock_excel(
    tenant_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = await rd.get_stock_report_data(db, tenant_id=tenant_id, category_id=category_id, product_id=product_id)
    return excel_response(generate_excel(rows, "Stock"), f"stock_{_now_str()}")


@router.get("/stock/pdf")
async def stock_pdf(
    tenant_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = await rd.get_stock_report_data(db, tenant_id=tenant_id, category_id=category_id, product_id=product_id)
    return pdf_response(generate_pdf(rows, "Stock Report"), f"stock_{_now_str()}")


@router.get("/stock/low-stock/excel")
async def low_stock_excel(
    threshold: int = Query(default=10),
    tenant_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = await rd.get_low_stock_report_data(db, threshold=threshold, tenant_id=tenant_id, category_id=category_id)
    return excel_response(generate_excel(rows, "Low Stock"), f"low_stock_{_now_str()}")


@router.get("/stock/low-stock/pdf")
async def low_stock_pdf(
    threshold: int = Query(default=10),
    tenant_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = await rd.get_low_stock_report_data(db, threshold=threshold, tenant_id=tenant_id, category_id=category_id)
    return pdf_response(generate_pdf(rows, "Low Stock Report"), f"low_stock_{_now_str()}")


# ── Products ───────────────────────────────────────────────────────────────────

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
    rows = await rd.get_product_report_data(
        db, tenant_id=tenant_id, category_id=category_id,
        is_active=is_active, date_from=date_from, date_to=date_to,
    )
    return excel_response(generate_excel(rows, "Products"), f"products_{_now_str()}")


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
    rows = await rd.get_product_report_data(
        db, tenant_id=tenant_id, category_id=category_id,
        is_active=is_active, date_from=date_from, date_to=date_to,
    )
    return pdf_response(generate_pdf(rows, "Products Report"), f"products_{_now_str()}")


# ── Users ──────────────────────────────────────────────────────────────────────

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
    rows = await rd.get_user_report_data(
        db, role_id=role_id, tenant_id=tenant_id,
        district_id=district_id, state_id=state_id, is_active=is_active,
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
    rows = await rd.get_user_report_data(
        db, role_id=role_id, tenant_id=tenant_id,
        district_id=district_id, state_id=state_id, is_active=is_active,
    )
    return pdf_response(generate_pdf(rows, "Users Report"), f"users_{_now_str()}")


# ── Executive Performance ──────────────────────────────────────────────────────

@router.get("/executives/summary", response_model=CommonResponse)
async def executive_summary(
    year: int | None = None,
    month: int | None = None,
    tenant_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.utcnow()
    data = await rd.get_executive_summary(
        db, year=year or now.year, month=month or now.month, tenant_id=tenant_id
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
    now = datetime.utcnow()
    rows = await rd.get_executive_performance_data(
        db, year=year or now.year, month=month or now.month,
        tenant_id=tenant_id, district_id=district_id, state_id=state_id,
    )
    return excel_response(generate_excel(rows, "Executive Performance"), f"executive_performance_{_now_str()}")


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
    now = datetime.utcnow()
    rows = await rd.get_executive_performance_data(
        db, year=year or now.year, month=month or now.month,
        tenant_id=tenant_id, district_id=district_id, state_id=state_id,
    )
    return pdf_response(generate_pdf(rows, "Executive Performance Report"), f"executive_performance_{_now_str()}")


# ── Distributors ───────────────────────────────────────────────────────────────

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
    rows = await rd.get_distributor_report_data(
        db, date_from=date_from, date_to=date_to,
        tenant_id=tenant_id, district_id=district_id, state_id=state_id,
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
    rows = await rd.get_distributor_report_data(
        db, date_from=date_from, date_to=date_to,
        tenant_id=tenant_id, district_id=district_id, state_id=state_id,
    )
    return pdf_response(generate_pdf(rows, "Distributor Report"), f"distributors_{_now_str()}")


# ── Shops ──────────────────────────────────────────────────────────────────────

@router.get("/shops/summary", response_model=CommonResponse)
async def shop_summary(
    state_id: uuid.UUID | None = None,
    district_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await rd.get_shop_summary(db, state_id=state_id, district_id=district_id)
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
    rows = await rd.get_shop_report_data(
        db, date_from=date_from, date_to=date_to,
        tenant_id=tenant_id, state_id=state_id,
        district_id=district_id, taluk_id=taluk_id, is_ebo=is_ebo,
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
    rows = await rd.get_shop_report_data(
        db, date_from=date_from, date_to=date_to,
        tenant_id=tenant_id, state_id=state_id,
        district_id=district_id, taluk_id=taluk_id, is_ebo=is_ebo,
    )
    return pdf_response(generate_pdf(rows, "Shop Report"), f"shops_{_now_str()}")


# ── Returns ────────────────────────────────────────────────────────────────────

@router.get("/returns/excel")
async def returns_excel(
    date_from: date | None = None,
    date_to: date | None = None,
    tenant_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = await rd.get_returns_report_data(
        db, date_from=date_from, date_to=date_to,
        tenant_id=tenant_id, product_id=product_id,
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
    rows = await rd.get_returns_report_data(
        db, date_from=date_from, date_to=date_to,
        tenant_id=tenant_id, product_id=product_id,
    )
    return pdf_response(generate_pdf(rows, "Returns Report"), f"returns_{_now_str()}")