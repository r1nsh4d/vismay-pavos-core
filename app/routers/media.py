import uuid
from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.product import ProductVariant
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import CommonResponse, ResponseModel
from app.services.storage_service import upload_variant_image, delete_variant_image
from app.core.exceptions import AppException

router = APIRouter(prefix="/media", tags=["Media"])


@router.post("/variant-image/{variant_id}", response_model=CommonResponse)
async def upload_variant_image_endpoint(
    variant_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 1. Fetch the variant
    result = await db.execute(
        select(ProductVariant).where(
            ProductVariant.id == variant_id,
            ProductVariant.is_deleted == False,
        )
    )
    variant = result.scalar_one_or_none()
    if not variant:
        raise AppException(status_code=404, detail="Variant not found")

    # 2. If variant already has images, delete old ones from OSS first
    if variant.image_url or variant.thumbnail_url:
        await delete_variant_image(variant.image_url, variant.thumbnail_url)

    # 3. Upload new image + thumbnail to OSS
    file_bytes = await file.read()
    try:
        upload_result = await upload_variant_image(
            file_bytes=file_bytes,
            content_type=file.content_type,
            variant_id=str(variant_id),
        )
    except ValueError as e:
        raise AppException(status_code=400, detail=str(e))

    # 4. Save URLs into the variant row
    variant.image_url = upload_result["image_url"]
    variant.thumbnail_url = upload_result["thumbnail_url"]
    await db.flush()
    await db.commit()

    return ResponseModel(
        data=upload_result,
        message="Image uploaded successfully",
    )