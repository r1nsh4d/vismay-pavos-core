import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.common import CommonResponse, ResponseModel, ErrorResponseModel
from app.schemas.stock import StockUpdate, StockResponse
from app.services import stocks as stock_svc

router = APIRouter(prefix="/stocks", tags=["Stocks"])


@router.get("/variant/{variant_id}", response_model=CommonResponse)
async def get_stock(variant_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    stock = await stock_svc.get_stock_by_variant(db, variant_id)
    if not stock:
        return ErrorResponseModel(code=404, message="Stock not found", error={})
    return ResponseModel(data=StockResponse.model_validate(stock), message="Stock fetched")


@router.put("/variant/{variant_id}", response_model=CommonResponse)
async def set_stock(variant_id: uuid.UUID, stock_in: StockUpdate, db: AsyncSession = Depends(get_db)):
    stock = await stock_svc.set_stock(db, variant_id, stock_in)
    return ResponseModel(data=StockResponse.model_validate(stock), message="Stock updated")