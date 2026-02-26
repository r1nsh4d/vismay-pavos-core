from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.database import get_db
from app.dependencies import get_current_user
from app.models.product import Product, ProductDetail
from app.schemas.common import ResponseModel, PaginatedResponse
from app.schemas.product import ProductCreate, ProductResponse, ProductSummary, ProductUpdate

router = APIRouter(prefix="/products", tags=["Products"])


# ─── List Products (with filters) ────────────────────────────────────────────

@router.get("")
async def list_products(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    tenant_id: int | None = Query(None),
    category_id: int | None = Query(None),
    is_active: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    offset = (page - 1) * limit
    query = select(Product).options(selectinload(Product.details))
    count_query = select(func.count()).select_from(Product)

    if tenant_id:
        query = query.where(Product.tenant_id == tenant_id)
        count_query = count_query.where(Product.tenant_id == tenant_id)
    if category_id:
        query = query.where(Product.category_id == category_id)
        count_query = count_query.where(Product.category_id == category_id)
    if is_active is not None:
        query = query.where(Product.is_active == is_active)
        count_query = count_query.where(Product.is_active == is_active)

    total = await db.scalar(count_query)
    result = await db.execute(query.offset(offset).limit(limit))
    items = [ProductResponse.model_validate(p).model_dump() for p in result.scalars().all()]

    return PaginatedResponse(
        data=items,
        message="Products fetched successfully",
        limit=limit,
        page=page,
        total=total
    )


# ─── List by Tenant ───────────────────────────────────────────────────────────

@router.get("/tenant/{tenant_id}")
async def list_products_by_tenant(
    tenant_id: int,
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    offset = (page - 1) * limit
    query = select(Product).options(selectinload(Product.details)).where(Product.tenant_id == tenant_id)
    count_query = select(func.count()).select_from(Product).where(Product.tenant_id == tenant_id)

    if is_active is not None:
        query = query.where(Product.is_active == is_active)
        count_query = count_query.where(Product.is_active == is_active)

    total = await db.scalar(count_query)
    result = await db.execute(query.offset(offset).limit(limit))
    items = [ProductResponse.model_validate(p).model_dump() for p in result.scalars().all()]

    return PaginatedResponse(
        data=items,
        message="Products fetched successfully",
        limit=limit,
        page=page,
        total=total
    )


# ─── List by Category ─────────────────────────────────────────────────────────

@router.get("/category/{category_id}")
async def list_products_by_category(
    category_id: int,
    tenant_id: int | None = Query(None),
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    offset = (page - 1) * limit
    query = select(Product).options(selectinload(Product.details)).where(Product.category_id == category_id)
    count_query = select(func.count()).select_from(Product).where(Product.category_id == category_id)

    if tenant_id:
        query = query.where(Product.tenant_id == tenant_id)
        count_query = count_query.where(Product.tenant_id == tenant_id)
    if is_active is not None:
        query = query.where(Product.is_active == is_active)
        count_query = count_query.where(Product.is_active == is_active)

    total = await db.scalar(count_query)
    result = await db.execute(query.offset(offset).limit(limit))
    items = [ProductResponse.model_validate(p).model_dump() for p in result.scalars().all()]

    return PaginatedResponse(
        data=items,
        message="Products fetched successfully",
        limit=limit,
        page=page,
        total=total
    )


# ─── List for Stock Entry (summary, tenant + category filter) ─────────────────
# This is used when adding stock — shows products with their details (sizes/pieces)
# so the user can select a product and enter box count.

@router.get("/stock-select")
async def list_products_for_stock(
    tenant_id: int = Query(...),
    category_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    query = (
        select(Product)
        .options(selectinload(Product.details))
        .where(Product.tenant_id == tenant_id, Product.is_active == True)
    )
    if category_id:
        query = query.where(Product.category_id == category_id)

    result = await db.execute(query)
    items = [ProductSummary.model_validate(p).model_dump() for p in result.scalars().all()]

    return ResponseModel(data=items, message="Products fetched for stock entry")


# ─── Get by ID ────────────────────────────────────────────────────────────────

@router.get("/{product_id}")
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(
        select(Product).options(selectinload(Product.details)).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise AppException(status_code=404, detail="Product not found", error_code="NOT_FOUND")

    return ResponseModel(
        data=ProductResponse.model_validate(product).model_dump(),
        message="Product fetched successfully",
    )


# ─── Create ───────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_product(
    payload: ProductCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    existing = await db.scalar(select(Product).where(Product.box_code == payload.box_code))
    if existing:
        raise AppException(status_code=409, detail="Box code already exists", error_code="DUPLICATE_BOX_CODE")

    product = Product(**payload.model_dump(exclude={"details"}))
    db.add(product)
    await db.flush()

    for d in payload.details:
        db.add(ProductDetail(product_id=product.id, **d.model_dump()))
    await db.flush()

    result = await db.execute(
        select(Product).options(selectinload(Product.details)).where(Product.id == product.id)
    )
    return ResponseModel(
        data=ProductResponse.model_validate(result.scalar_one()).model_dump(),
        message="Product created successfully",
    )


# ─── Update ───────────────────────────────────────────────────────────────────

@router.patch("/{product_id}")
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(
        select(Product).options(selectinload(Product.details)).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise AppException(status_code=404, detail="Product not found", error_code="NOT_FOUND")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)

    await db.flush()
    await db.refresh(product)

    return ResponseModel(
        data=ProductResponse.model_validate(product).model_dump(),
        message="Product updated successfully",
    )


# ─── Activate ─────────────────────────────────────────────────────────────────

@router.patch("/{product_id}/activate")
async def activate_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    product = await db.scalar(select(Product).where(Product.id == product_id))
    if not product:
        raise AppException(status_code=404, detail="Product not found", error_code="NOT_FOUND")
    if product.is_active:
        raise AppException(status_code=400, detail="Product is already active", error_code="ALREADY_ACTIVE")

    product.is_active = True
    await db.flush()

    return ResponseModel(data={"id": product_id, "is_active": True}, message="Product activated successfully")


# ─── Deactivate ───────────────────────────────────────────────────────────────

@router.patch("/{product_id}/deactivate")
async def deactivate_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    product = await db.scalar(select(Product).where(Product.id == product_id))
    if not product:
        raise AppException(status_code=404, detail="Product not found", error_code="NOT_FOUND")
    if not product.is_active:
        raise AppException(status_code=400, detail="Product is already inactive", error_code="ALREADY_INACTIVE")

    product.is_active = False
    await db.flush()

    return ResponseModel(data={"id": product_id, "is_active": False}, message="Product deactivated successfully")


# ─── Delete ───────────────────────────────────────────────────────────────────

@router.delete("/{product_id}")
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    product = await db.scalar(select(Product).where(Product.id == product_id))
    if not product:
        raise AppException(status_code=404, detail="Product not found", error_code="NOT_FOUND")

    await db.delete(product)
    await db.flush()

    return ResponseModel(data=[], message="Product deleted successfully")