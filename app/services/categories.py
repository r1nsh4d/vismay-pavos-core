import uuid
from typing import List, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate


async def get_category_by_id(db: AsyncSession, category_id: uuid.UUID) -> Category | None:
    result = await db.execute(select(Category).where(Category.id == category_id))
    return result.scalar_one_or_none()


async def get_all_categories(
    db: AsyncSession,
    tenant_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    page: int = 1,
    limit: int = 20,
) -> Tuple[List[Category], int]:
    query = select(Category)
    if tenant_id:
        query = query.where(Category.tenant_id == tenant_id)
    if is_active is not None:
        query = query.where(Category.is_active == is_active)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    result = await db.execute(query.offset((page - 1) * limit).limit(limit))
    return result.scalars().all(), total


async def create_category(db: AsyncSession, cat_in: CategoryCreate) -> Category:
    cat = Category(**cat_in.model_dump())
    db.add(cat)
    await db.flush()
    return cat


async def update_category(db: AsyncSession, cat: Category, cat_in: CategoryUpdate) -> Category:
    for field, value in cat_in.model_dump(exclude_unset=True).items():
        setattr(cat, field, value)
    await db.flush()
    return cat


async def delete_category(db: AsyncSession, cat: Category) -> None:
    await db.delete(cat)
    await db.flush()