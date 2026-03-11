import uuid
from typing import List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.common import CommonResponse, ErrorResponseModel, ResponseModel, PaginatedResponse
from app.schemas.shop import ShopCreate, ShopUpdate
from app.services import shops as shop_svc

router = APIRouter(prefix="/shops", tags=["Shops"])


def _parse_uuids(val: str | None) -> List[uuid.UUID]:
    if not val:
        return []
    try:
        return [uuid.UUID(v.strip()) for v in val.split(",") if v.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID in query parameter")


@router.get("/search", response_model=CommonResponse)
async def search_shops(
    q: str | None = Query(default=None, description="Search by name, contact person"),
    district_ids: str | None = Query(default=None, description="Comma-separated district UUIDs"),
    taluk_ids: str | None = Query(default=None, description="Comma-separated taluk UUIDs"),
    is_active: bool | None = None,
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    shops, total = await shop_svc.search_shops(
        db,
        q=q,
        district_ids=_parse_uuids(district_ids),
        taluk_ids=_parse_uuids(taluk_ids),
        is_active=is_active,
        page=page,
        limit=limit,
    )
    return PaginatedResponse(
        data=[shop_svc.serialize_shop(s) for s in shops],
        message="Shops fetched successfully",
        page=page,
        limit=limit,
        total=total,
    )


@router.post("", response_model=CommonResponse)
async def create_shop(shop_in: ShopCreate, db: AsyncSession = Depends(get_db)):
    shop = await shop_svc.create_shop(db, shop_in)
    return ResponseModel(data=shop_svc.serialize_shop(shop), message="Shop created successfully")


@router.get("/{shop_id}", response_model=CommonResponse)
async def get_shop(shop_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    shop = await shop_svc.get_shop_by_id(db, shop_id)
    if not shop:
        return ErrorResponseModel(code=404, message="Shop not found", error={})
    return ResponseModel(data=shop_svc.serialize_shop(shop), message="Shop fetched successfully")


@router.put("/{shop_id}", response_model=CommonResponse)
async def update_shop(shop_id: uuid.UUID, shop_in: ShopUpdate, db: AsyncSession = Depends(get_db)):
    shop = await shop_svc.get_shop_by_id(db, shop_id)
    if not shop:
        return ErrorResponseModel(code=404, message="Shop not found", error={})
    shop = await shop_svc.update_shop(db, shop, shop_in)
    return ResponseModel(data=shop_svc.serialize_shop(shop), message="Shop updated successfully")


@router.patch("/{shop_id}/toggle", response_model=CommonResponse)
async def toggle_shop(shop_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    shop = await shop_svc.get_shop_by_id(db, shop_id)
    if not shop:
        return ErrorResponseModel(code=404, message="Shop not found", error={})
    shop.is_active = not shop.is_active
    return ResponseModel(
        data=shop_svc.serialize_shop(shop),
        message=f"Shop {'activated' if shop.is_active else 'deactivated'} successfully",
    )


@router.delete("/{shop_id}", response_model=CommonResponse)
async def delete_shop(shop_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    shop = await shop_svc.get_shop_by_id(db, shop_id)
    if not shop:
        return ErrorResponseModel(code=404, message="Shop not found", error={})
    await shop_svc.delete_shop(db, shop)
    return ResponseModel(data=None, message="Shop deleted successfully")