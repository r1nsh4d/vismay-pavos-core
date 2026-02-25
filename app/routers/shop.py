from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.database import get_db
from app.dependencies import get_current_user
from app.models.district import District
from app.models.shop import Shop
from app.models.user import User
from app.schemas.common import ResponseModel
from app.schemas.shop import ShopCreate, ShopResponse, ShopUpdate

router = APIRouter(prefix="/shops", tags=["Shops"])


# ─── List All (admin use, all filters) ───────────────────────────────────────

@router.get("")
async def list_shops(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    district_id: int | None = Query(None),
    is_active: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    offset = (page - 1) * page_size
    query = select(Shop)
    count_query = select(func.count()).select_from(Shop)

    if district_id is not None:
        query = query.where(Shop.district_id == district_id)
        count_query = count_query.where(Shop.district_id == district_id)
    if is_active is not None:
        query = query.where(Shop.is_active == is_active)
        count_query = count_query.where(Shop.is_active == is_active)

    total = await db.scalar(count_query)
    result = await db.execute(query.offset(offset).limit(page_size))
    shops = [ShopResponse.model_validate(s).model_dump() for s in result.scalars().all()]

    return ResponseModel(
        data={"total": total, "page": page, "page_size": page_size, "results": shops},
        message="Shops fetched successfully",
    )


# ─── List by District (executive primary use case) ───────────────────────────
# Executive calls this with their own district_id to see all shops they can order for

@router.get("/district/{district_id}")
async def list_shops_by_district(
    district_id: int,
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate district exists
    district = await db.scalar(select(District).where(District.id == district_id))
    if not district:
        raise AppException(status_code=404, detail="District not found", error_code="NOT_FOUND")

    offset = (page - 1) * page_size
    query = select(Shop).where(Shop.district_id == district_id)
    count_query = select(func.count()).select_from(Shop).where(Shop.district_id == district_id)

    if is_active is not None:
        query = query.where(Shop.is_active == is_active)
        count_query = count_query.where(Shop.is_active == is_active)

    total = await db.scalar(count_query)
    result = await db.execute(query.offset(offset).limit(page_size))
    shops = [ShopResponse.model_validate(s).model_dump() for s in result.scalars().all()]

    return ResponseModel(
        data={"total": total, "page": page, "page_size": page_size, "results": shops},
        message="Shops fetched successfully",
    )


# ─── List shops in current user's district ───────────────────────────────────
# Shortcut for executive — no need to pass district_id manually

@router.get("/my-district")
async def list_my_district_shops(
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.district_id:
        raise AppException(
            status_code=400,
            detail="Your account is not assigned to any district",
            error_code="NO_DISTRICT",
        )

    offset = (page - 1) * page_size
    query = select(Shop).where(Shop.district_id == current_user.district_id)
    count_query = select(func.count()).select_from(Shop).where(Shop.district_id == current_user.district_id)

    if is_active is not None:
        query = query.where(Shop.is_active == is_active)
        count_query = count_query.where(Shop.is_active == is_active)

    total = await db.scalar(count_query)
    result = await db.execute(query.offset(offset).limit(page_size))
    shops = [ShopResponse.model_validate(s).model_dump() for s in result.scalars().all()]

    return ResponseModel(
        data={"total": total, "page": page, "page_size": page_size, "results": shops},
        message="Shops fetched successfully",
    )


# ─── Get by ID ────────────────────────────────────────────────────────────────

@router.get("/{shop_id}")
async def get_shop(
    shop_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    shop = await db.scalar(select(Shop).where(Shop.id == shop_id))
    if not shop:
        raise AppException(status_code=404, detail="Shop not found", error_code="NOT_FOUND")

    return ResponseModel(
        data=ShopResponse.model_validate(shop).model_dump(),
        message="Shop fetched successfully",
    )


# ─── Create ───────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_shop(
    payload: ShopCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate district exists
    district = await db.scalar(select(District).where(District.id == payload.district_id))
    if not district:
        raise AppException(status_code=404, detail="District not found", error_code="NOT_FOUND")

    # Duplicate shop name check within same district
    existing = await db.scalar(
        select(Shop).where(
            Shop.district_id == payload.district_id,
            Shop.name == payload.name,
        )
    )
    if existing:
        raise AppException(
            status_code=409,
            detail="Shop name already exists in this district",
            error_code="DUPLICATE_NAME",
        )

    shop = Shop(**payload.model_dump(), created_by=current_user.id)
    db.add(shop)
    await db.flush()
    await db.refresh(shop)

    return ResponseModel(
        data=ShopResponse.model_validate(shop).model_dump(),
        message="Shop created successfully",
    )


# ─── Update ───────────────────────────────────────────────────────────────────

@router.patch("/{shop_id}")
async def update_shop(
    shop_id: int,
    payload: ShopUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    shop = await db.scalar(select(Shop).where(Shop.id == shop_id))
    if not shop:
        raise AppException(status_code=404, detail="Shop not found", error_code="NOT_FOUND")

    # Duplicate name check within same district if name is changing
    if payload.name and payload.name != shop.name:
        duplicate = await db.scalar(
            select(Shop).where(
                Shop.district_id == shop.district_id,
                Shop.name == payload.name,
                Shop.id != shop_id,
            )
        )
        if duplicate:
            raise AppException(
                status_code=409,
                detail="Shop name already exists in this district",
                error_code="DUPLICATE_NAME",
            )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(shop, field, value)

    await db.flush()
    await db.refresh(shop)

    return ResponseModel(
        data=ShopResponse.model_validate(shop).model_dump(),
        message="Shop updated successfully",
    )


# ─── Activate ─────────────────────────────────────────────────────────────────

@router.patch("/{shop_id}/activate")
async def activate_shop(
    shop_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    shop = await db.scalar(select(Shop).where(Shop.id == shop_id))
    if not shop:
        raise AppException(status_code=404, detail="Shop not found", error_code="NOT_FOUND")
    if shop.is_active:
        raise AppException(status_code=400, detail="Shop is already active", error_code="ALREADY_ACTIVE")

    shop.is_active = True
    await db.flush()

    return ResponseModel(data={"id": shop_id, "is_active": True}, message="Shop activated successfully")


# ─── Deactivate ───────────────────────────────────────────────────────────────

@router.patch("/{shop_id}/deactivate")
async def deactivate_shop(
    shop_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    shop = await db.scalar(select(Shop).where(Shop.id == shop_id))
    if not shop:
        raise AppException(status_code=404, detail="Shop not found", error_code="NOT_FOUND")
    if not shop.is_active:
        raise AppException(status_code=400, detail="Shop is already inactive", error_code="ALREADY_INACTIVE")

    shop.is_active = False
    await db.flush()

    return ResponseModel(data={"id": shop_id, "is_active": False}, message="Shop deactivated successfully")


# ─── Delete ───────────────────────────────────────────────────────────────────

@router.delete("/{shop_id}")
async def delete_shop(
    shop_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    shop = await db.scalar(select(Shop).where(Shop.id == shop_id))
    if not shop:
        raise AppException(status_code=404, detail="Shop not found", error_code="NOT_FOUND")

    await db.delete(shop)
    await db.flush()

    return ResponseModel(data=[], message="Shop deleted successfully")