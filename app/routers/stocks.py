import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.common import CommonResponse, ResponseModel, ErrorResponseModel
from app.schemas.stock import (
    IndividualStockAdd, BundleStockAdd,
    SetTypeStockResponse,
)
from app.services import stocks as stock_svc
from app.services.stocks import serialize_stock

router = APIRouter(prefix="/stocks", tags=["Stocks"])


@router.get("/set-type", response_model=CommonResponse)
async def get_stock_by_set_type(
    product_id: uuid.UUID,
    set_type_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await stock_svc.get_stock_by_set_type(db, product_id, set_type_id)
    return ResponseModel(
        data=SetTypeStockResponse(**result),
        message="Stock fetched by set type",
    )

@router.get("/variant/{variant_id}", response_model=CommonResponse)
async def get_stock(variant_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    stock = await stock_svc.get_stock_by_variant(db, variant_id)
    if not stock:
        return ErrorResponseModel(code=404, message="Stock not found", error={})
    return ResponseModel(data=serialize_stock(stock), message="Stock fetched")


@router.post("/add/individual", response_model=CommonResponse)
async def add_individual_stock(stock_in: IndividualStockAdd, db: AsyncSession = Depends(get_db)):
    stock = await stock_svc.add_individual_stock(db, stock_in)
    await db.commit()
    return ResponseModel(data=serialize_stock(stock), message="Individual stock added")


@router.post("/add/bundle", response_model=CommonResponse)
async def add_bundle_stock(stock_in: BundleStockAdd, db: AsyncSession = Depends(get_db)):
    updated_stocks = await stock_svc.add_bundle_stock(db, stock_in)
    await db.commit()
    # Re-query after commit with full eager loading
    reloaded = [await stock_svc.get_stock_by_id(db, s.id) for s in updated_stocks]
    return ResponseModel(
        data=[serialize_stock(s) for s in reloaded],
        message=f"Bundle stock added across {len(reloaded)} variants",
    )