# app/routes/category.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.database import get_db
from app.dependencies import get_current_user
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/categories", tags=["Categories"])


# ─── List All (with optional filters) ────────────────────────────────────────

@router.get("")
async def list_categories(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    offset = (page - 1) * page_size
    query = select(Category)
    count_query = select(func.count()).select_from(Category)

    if tenant_id:
        query = query.where(Category.tenant_id == tenant_id)
        count_query = count_query.where(Category.tenant_id == tenant_id)

    total = await db.scalar(count_query)
    result = await db.execute(query.offset(offset).limit(page_size))
    cats = [CategoryResponse.model_validate(c).model_dump() for c in result.scalars().all()]

    return ResponseModel(
        data={"total": total, "page": page, "page_size": page_size, "results": cats},
        message="Categories fetched successfully",
    )


# ─── List by Tenant ───────────────────────────────────────────────────────────

@router.get("/tenant/{tenant_id}")
async def list_categories_by_tenant(
    tenant_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    offset = (page - 1) * page_size
    query = select(Category).where(Category.tenant_id == tenant_id)
    count_query = select(func.count()).select_from(Category).where(Category.tenant_id == tenant_id)

    total = await db.scalar(count_query)
    result = await db.execute(query.offset(offset).limit(page_size))
    cats = [CategoryResponse.model_validate(c).model_dump() for c in result.scalars().all()]

    return ResponseModel(
        data={"total": total, "page": page, "page_size": page_size, "results": cats},
        message="Categories fetched successfully",
    )


# ─── Get by ID ────────────────────────────────────────────────────────────────

@router.get("/{category_id}")
async def get_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    cat = await db.scalar(select(Category).where(Category.id == category_id))
    if not cat:
        raise AppException(status_code=404, detail="Category not found", error_code="NOT_FOUND")

    return ResponseModel(
        data=CategoryResponse.model_validate(cat).model_dump(),
        message="Category fetched successfully",
    )


# ─── Create ───────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_category(
    payload: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    existing = await db.scalar(
        select(Category).where(
            Category.tenant_id == payload.tenant_id,
            Category.name == payload.name,
        )
    )
    if existing:
        raise AppException(status_code=409, detail="Category name already exists for this tenant", error_code="DUPLICATE_NAME")

    cat = Category(**payload.model_dump())
    db.add(cat)
    await db.flush()
    await db.refresh(cat)

    return ResponseModel(
        data=CategoryResponse.model_validate(cat).model_dump(),
        message="Category created successfully",
    )


# ─── Update ───────────────────────────────────────────────────────────────────

@router.patch("/{category_id}")
async def update_category(
    category_id: int,
    payload: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    cat = await db.scalar(select(Category).where(Category.id == category_id))
    if not cat:
        raise AppException(status_code=404, detail="Category not found", error_code="NOT_FOUND")

    # Check duplicate name within same tenant if name is being updated
    if payload.name:
        duplicate = await db.scalar(
            select(Category).where(
                Category.tenant_id == cat.tenant_id,
                Category.name == payload.name,
                Category.id != category_id,
            )
        )
        if duplicate:
            raise AppException(status_code=409, detail="Category name already exists for this tenant", error_code="DUPLICATE_NAME")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(cat, field, value)

    await db.flush()
    await db.refresh(cat)

    return ResponseModel(
        data=CategoryResponse.model_validate(cat).model_dump(),
        message="Category updated successfully",
    )


# ─── Delete ───────────────────────────────────────────────────────────────────

@router.delete("/{category_id}")
async def delete_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    cat = await db.scalar(select(Category).where(Category.id == category_id))
    if not cat:
        raise AppException(status_code=404, detail="Category not found", error_code="NOT_FOUND")

    await db.delete(cat)
    await db.flush()

    return ResponseModel(data=[], message="Category deleted successfully")