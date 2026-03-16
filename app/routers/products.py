import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.common import CommonResponse, ResponseModel, ErrorResponseModel, PaginatedResponse
from app.schemas.product import ProductCreate, ProductUpdate, ProductVariantCreate, ProductVariantResponse
from app.services import products as product_svc
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("/search", response_model=CommonResponse)
async def search_products(
    q: str | None = None,
    tenant_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    model_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    products, total = await product_svc.search_products(
        db, q=q, tenant_id=tenant_id, category_id=category_id,
        model_id=model_id, is_active=is_active, page=page, limit=limit,
    )
    return PaginatedResponse(
        data=[product_svc.serialize_product(p) for p in products],
        message="Products fetched", page=page, limit=limit, total=total,
    )


@router.post("", response_model=CommonResponse)
async def create_product(
    product_in: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = await product_svc.create_product(db, product_in)
    await db.commit()
    product = await product_svc.get_product_by_id(db, product.id)
    return ResponseModel(data=product_svc.serialize_product(product), message="Product created")


@router.get("/{product_id}", response_model=CommonResponse)
async def get_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = await product_svc.get_product_by_id(db, product_id)
    if not product:
        return ErrorResponseModel(code=404, message="Product not found", error={})
    return ResponseModel(data=product_svc.serialize_product(product), message="Product fetched")


@router.put("/{product_id}", response_model=CommonResponse)
async def update_product(
    product_id: uuid.UUID,
    product_in: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = await product_svc.get_product_by_id(db, product_id)
    if not product:
        return ErrorResponseModel(code=404, message="Product not found", error={})
    product = await product_svc.update_product(db, product, product_in)
    await db.commit()
    product = await product_svc.get_product_by_id(db, product.id)
    return ResponseModel(data=product_svc.serialize_product(product), message="Product updated")


@router.delete("/{product_id}", response_model=CommonResponse)
async def delete_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = await product_svc.get_product_by_id(db, product_id)
    if not product:
        return ErrorResponseModel(code=404, message="Product not found", error={})
    await product_svc.delete_product(db, product)
    await db.commit()
    return ResponseModel(data=None, message="Product deleted")


@router.post("/{product_id}/variants", response_model=CommonResponse)
async def add_variant(
    product_id: uuid.UUID,
    variant_in: ProductVariantCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = await product_svc.get_product_by_id(db, product_id)
    if not product:
        return ErrorResponseModel(code=404, message="Product not found", error={})
    variant = await product_svc.add_variant(db, product_id, variant_in)
    await db.commit()
    return ResponseModel(data={"id": str(variant.id)}, message="Variant added")


@router.put("/{product_id}/variants/{variant_id}", response_model=CommonResponse)
async def update_variant(
    product_id: uuid.UUID,
    variant_id: uuid.UUID,
    variant_in: ProductVariantCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = await product_svc.get_product_by_id(db, product_id)
    if not product:
        return ErrorResponseModel(code=404, message="Product not found", error={})
    variant = await product_svc.update_variant(db, product_id, variant_id, variant_in)
    if not variant:
        return ErrorResponseModel(code=404, message="Variant not found", error={})
    await db.commit()
    return ResponseModel(data=ProductVariantResponse.model_validate(variant), message="Variant updated")


@router.delete("/{product_id}/variants/{variant_id}", response_model=CommonResponse)
async def delete_variant(
    product_id: uuid.UUID,
    variant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = await product_svc.get_product_by_id(db, product_id)
    if not product:
        return ErrorResponseModel(code=404, message="Product not found", error={})
    deleted = await product_svc.delete_variant(db, product_id, variant_id)
    if not deleted:
        return ErrorResponseModel(code=404, message="Variant not found", error={})
    await db.commit()
    return ResponseModel(data=None, message="Variant deleted")