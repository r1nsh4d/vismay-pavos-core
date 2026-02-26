<<<<<<< Updated upstream
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.database import get_db
from app.dependencies import get_current_user
from app.models.product import Product
from app.models.stock import Stock
from app.models.user import User
from app.schemas.common import ResponseModel, PaginatedResponse
from app.schemas.stock import StockCreate, StockResponse, StockSummaryResponse

router = APIRouter(prefix="/stocks", tags=["Stocks"])


@router.get("")
async def list_stocks(
    tenant_id: int | None = Query(None),
    product_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    offset = (page - 1) * limit
    query = select(Stock)
    count_query = select(func.count()).select_from(Stock)

    if tenant_id:
        query = query.where(Stock.tenant_id == tenant_id)
        count_query = count_query.where(Stock.tenant_id == tenant_id)
    if product_id:
        query = query.where(Stock.product_id == product_id)
        count_query = count_query.where(Stock.product_id == product_id)

    total = await db.scalar(count_query)
    result = await db.execute(query.order_by(Stock.created_at.asc()).offset(offset).limit(limit))
    stocks = [StockResponse.model_validate(s).model_dump() for s in result.scalars().all()]
    return PaginatedResponse(
        data=stocks,
        message="Stocks fetched successfully",
        page=page,
        limit=limit,
        total=total
    )


@router.get("/availability")
async def get_stock_availability(
    tenant_id: int = Query(...),
    category_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Executive uses this before placing order.
    Returns available box count per product for a tenant+category.
    """
    result = await db.execute(
        select(
            Stock.product_id,
            Product.name.label("product_name"),
            func.sum(Stock.boxes_available).label("boxes_available"),
        )
        .join(Product, Product.id == Stock.product_id)
        .where(
            Stock.tenant_id == tenant_id,
            Product.category_id == category_id,
            Stock.is_active == True,
        )
        .group_by(Stock.product_id, Product.name)
    )
    rows = result.all()
    data = [
        {
            "product_id": r.product_id,
            "product_name": r.product_name,
            "boxes_available": r.boxes_available or 0,
        }
        for r in rows
    ]
    return ResponseModel(data=data, message="Stock availability fetched successfully")


@router.get("/{stock_id}")
async def get_stock(stock_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stock = await db.scalar(select(Stock).where(Stock.id == stock_id))
    if not stock:
        raise AppException(status_code=404, detail="Stock not found", error_code="NOT_FOUND")
    return ResponseModel(data=StockResponse.model_validate(stock).model_dump(), message="Stock fetched successfully")


@router.post("", status_code=201)
async def add_stock(
    payload: StockCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stock = Stock(
        tenant_id=payload.tenant_id,
        product_id=payload.product_id,
        added_by=current_user.id,
        batch_ref=payload.batch_ref,
        boxes_total=payload.boxes_total,
        boxes_available=payload.boxes_total,  # all available on entry
        boxes_reserved=0,
        boxes_billed=0,
        boxes_dispatched=0,
    )
    db.add(stock)
    await db.flush()
    await db.refresh(stock)
    return ResponseModel(data=StockResponse.model_validate(stock).model_dump(), message="Stock added successfully")


@router.delete("/{stock_id}")
async def delete_stock(stock_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stock = await db.scalar(select(Stock).where(Stock.id == stock_id))
    if not stock:
        raise AppException(status_code=404, detail="Stock not found", error_code="NOT_FOUND")
    if stock.boxes_reserved > 0 or stock.boxes_billed > 0:
        raise AppException(
            status_code=400,
            detail="Cannot delete stock with reserved or billed boxes",
            error_code="STOCK_IN_USE",
        )
    await db.delete(stock)
    await db.flush()
=======
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.database import get_db
from app.dependencies import get_current_user
from app.models.product import Product
from app.models.stock import Stock
from app.models.user import User
from app.schemas.common import ResponseModel, PaginatedResponse
from app.schemas.stock import StockCreate, StockResponse, StockSummaryResponse

router = APIRouter(prefix="/stocks", tags=["Stocks"])


@router.get("")
async def list_stocks(
    tenant_id: int | None = Query(None),
    product_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    offset = (page - 1) * limit
    query = select(Stock)
    count_query = select(func.count()).select_from(Stock)

    if tenant_id:
        query = query.where(Stock.tenant_id == tenant_id)
        count_query = count_query.where(Stock.tenant_id == tenant_id)
    if product_id:
        query = query.where(Stock.product_id == product_id)
        count_query = count_query.where(Stock.product_id == product_id)

    total = await db.scalar(count_query)
    result = await db.execute(query.order_by(Stock.created_at.asc()).offset(offset).limit(limit))
    stocks = [StockResponse.model_validate(s).model_dump() for s in result.scalars().all()]
    return PaginatedResponse(
        data=stocks,
        message="Stocks fetched successfully",
        page=page,
        limit=limit,
        total=total
    )


@router.get("/availability")
async def get_stock_availability(
    tenant_id: int = Query(...),
    category_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Executive uses this before placing order.
    Returns available box count per product for a tenant+category.
    """
    result = await db.execute(
        select(
            Stock.product_id,
            Product.name.label("product_name"),
            func.sum(Stock.boxes_available).label("boxes_available"),
        )
        .join(Product, Product.id == Stock.product_id)
        .where(
            Stock.tenant_id == tenant_id,
            Product.category_id == category_id,
            Stock.is_active == True,
        )
        .group_by(Stock.product_id, Product.name)
    )
    rows = result.all()
    data = [
        {
            "product_id": r.product_id,
            "product_name": r.product_name,
            "boxes_available": r.boxes_available or 0,
        }
        for r in rows
    ]
    return ResponseModel(data=data, message="Stock availability fetched successfully")


@router.get("/{stock_id}")
async def get_stock(stock_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stock = await db.scalar(select(Stock).where(Stock.id == stock_id))
    if not stock:
        raise AppException(status_code=404, detail="Stock not found", error_code="NOT_FOUND")
    return ResponseModel(data=StockResponse.model_validate(stock).model_dump(), message="Stock fetched successfully")


@router.post("", status_code=201)
async def add_stock(
    payload: StockCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stock = Stock(
        tenant_id=payload.tenant_id,
        product_id=payload.product_id,
        added_by=current_user.id,
        batch_ref=payload.batch_ref,
        boxes_total=payload.boxes_total,
        boxes_available=payload.boxes_total,  # all available on entry
        boxes_reserved=0,
        boxes_billed=0,
        boxes_dispatched=0,
    )
    db.add(stock)
    await db.flush()
    await db.refresh(stock)
    return ResponseModel(data=StockResponse.model_validate(stock).model_dump(), message="Stock added successfully")


@router.delete("/{stock_id}")
async def delete_stock(stock_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stock = await db.scalar(select(Stock).where(Stock.id == stock_id))
    if not stock:
        raise AppException(status_code=404, detail="Stock not found", error_code="NOT_FOUND")
    if stock.boxes_reserved > 0 or stock.boxes_billed > 0:
        raise AppException(
            status_code=400,
            detail="Cannot delete stock with reserved or billed boxes",
            error_code="STOCK_IN_USE",
        )
    await db.delete(stock)
    await db.flush()
>>>>>>> Stashed changes
    return ResponseModel(data=[], message="Stock deleted successfully")