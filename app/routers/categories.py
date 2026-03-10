import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.common import CommonResponse, ResponseModel, ErrorResponseModel
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryResponse
from app.services import categories as cat_svc

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.post("", response_model=CommonResponse)
async def create_category(cat_in: CategoryCreate, db: AsyncSession = Depends(get_db)):
    cat = await cat_svc.create_category(db, cat_in)
    return ResponseModel(data=CategoryResponse.model_validate(cat), message="Category created")


@router.get("", response_model=CommonResponse)
async def list_categories(
    tenant_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    cats, total = await cat_svc.get_all_categories(db, tenant_id=tenant_id, is_active=is_active, page=page, limit=limit)
    from app.schemas.common import PaginatedResponse
    return PaginatedResponse(data=[CategoryResponse.model_validate(c) for c in cats], message="Categories fetched", page=page, limit=limit, total=total)


@router.get("/{category_id}", response_model=CommonResponse)
async def get_category(category_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    cat = await cat_svc.get_category_by_id(db, category_id)
    if not cat:
        return ErrorResponseModel(code=404, message="Category not found", error={})
    return ResponseModel(data=CategoryResponse.model_validate(cat), message="Category fetched")


@router.put("/{category_id}", response_model=CommonResponse)
async def update_category(category_id: uuid.UUID, cat_in: CategoryUpdate, db: AsyncSession = Depends(get_db)):
    cat = await cat_svc.get_category_by_id(db, category_id)
    if not cat:
        return ErrorResponseModel(code=404, message="Category not found", error={})
    cat = await cat_svc.update_category(db, cat, cat_in)
    return ResponseModel(data=CategoryResponse.model_validate(cat), message="Category updated")


@router.delete("/{category_id}", response_model=CommonResponse)
async def delete_category(category_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    cat = await cat_svc.get_category_by_id(db, category_id)
    if not cat:
        return ErrorResponseModel(code=404, message="Category not found", error={})
    await cat_svc.delete_category(db, cat)
    return ResponseModel(data=None, message="Category deleted")