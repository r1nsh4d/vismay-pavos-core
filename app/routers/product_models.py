import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.common import CommonResponse, ResponseModel, ErrorResponseModel, PaginatedResponse
from app.schemas.product_model import ModelCreate, ModelUpdate
from app.services import product_model as model_svc
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/models", tags=["Models"])


@router.get("", response_model=CommonResponse)
async def get_models(
    category_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    models, total = await model_svc.get_models(
        db, category_id=category_id, is_active=is_active, page=page, limit=limit
    )
    return PaginatedResponse(
        data=[model_svc.serialize_model(m) for m in models],
        message="Models fetched", page=page, limit=limit, total=total,
    )


@router.post("", response_model=CommonResponse)
async def create_model(
    model_in: ModelCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = await model_svc.create_model(db, model_in)
    await db.commit()
    return ResponseModel(data=model_svc.serialize_model(model), message="Model created")


@router.get("/{model_id}", response_model=CommonResponse)
async def get_model(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = await model_svc.get_model_by_id(db, model_id)
    if not model:
        return ErrorResponseModel(code=404, message="Model not found", error={})
    return ResponseModel(data=model_svc.serialize_model(model), message="Model fetched")


@router.put("/{model_id}", response_model=CommonResponse)
async def update_model(
    model_id: uuid.UUID,
    model_in: ModelUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = await model_svc.get_model_by_id(db, model_id)
    if not model:
        return ErrorResponseModel(code=404, message="Model not found", error={})
    model = await model_svc.update_model(db, model, model_in)
    await db.commit()
    return ResponseModel(data=model_svc.serialize_model(model), message="Model updated")


@router.delete("/{model_id}", response_model=CommonResponse)
async def delete_model(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = await model_svc.get_model_by_id(db, model_id)
    if not model:
        return ErrorResponseModel(code=404, message="Model not found", error={})
    await model_svc.delete_model(db, model)
    await db.commit()
    return ResponseModel(data=None, message="Model deleted")