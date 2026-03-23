import uuid
from typing import Optional, List, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product_model import ProductModel
from app.schemas.product_model import ModelCreate, ModelUpdate


async def get_model_by_id(db: AsyncSession, model_id: uuid.UUID) -> Optional[ProductModel]:
    return await db.scalar(select(ProductModel).where(ProductModel.id == model_id))


async def get_models(
    db: AsyncSession,
    category_id: Optional[uuid.UUID] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    limit: int = 20,
) -> Tuple[List[ProductModel], int]:
    query = select(ProductModel)
    if category_id:
        query = query.where(ProductModel.category_id == category_id)
    if is_active is not None:
        query = query.where(ProductModel.is_active == is_active)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    result = await db.execute(query.offset((page - 1) * limit).limit(limit))
    return result.scalars().all(), total


async def create_model(db: AsyncSession, data: ModelCreate) -> ProductModel:
    model = ProductModel(**data.model_dump())
    db.add(model)
    await db.flush()
    return model


async def update_model(db: AsyncSession, model: ProductModel, data: ModelUpdate) -> ProductModel:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(model, field, value)
    await db.flush()
    return model


async def delete_model(db: AsyncSession, model: ProductModel) -> None:
    await db.delete(model)
    await db.flush()


def serialize_model(model: ProductModel) -> dict:
    return {
        "id": str(model.id),
        "categoryId": str(model.category_id),
        "name": model.name,
        "description": model.description,
        "isActive": model.is_active,
        "createdAt": model.created_at.isoformat(),
        "updatedAt": model.updated_at.isoformat(),
    }