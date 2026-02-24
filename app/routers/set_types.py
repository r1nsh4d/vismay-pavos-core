from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException
from app.database import get_db
from app.dependencies import get_current_user
from app.models.set_type import SetType, SetTypeDetail
from app.schemas.common import ResponseModel
from app.schemas.set_type import SetTypeCreate, SetTypeResponse, SetTypeUpdate

router = APIRouter(prefix="/set-types", tags=["Set Types"])


@router.get("")
async def list_set_types(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant_id: int | None = Query(None),
    category_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    offset = (page - 1) * page_size
    query = select(SetType).options(selectinload(SetType.details))
    count_query = select(func.count()).select_from(SetType)
    if tenant_id:
        query = query.where(SetType.tenant_id == tenant_id)
        count_query = count_query.where(SetType.tenant_id == tenant_id)
    if category_id:
        query = query.where(SetType.category_id == category_id)
        count_query = count_query.where(SetType.category_id == category_id)
    total = await db.scalar(count_query)
    result = await db.execute(query.offset(offset).limit(page_size))
    items = [SetTypeResponse.model_validate(s).model_dump() for s in result.scalars().all()]
    return ResponseModel(
        data={"total": total, "page": page, "page_size": page_size, "results": items},
        message="Set types fetched successfully",
    )


@router.post("", status_code=201)
async def create_set_type(
    payload: SetTypeCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    existing = await db.scalar(
        select(SetType).where(SetType.tenant_id == payload.tenant_id, SetType.name == payload.name)
    )
    if existing:
        raise AppException(status_code=409, detail="SetType name already exists for this tenant", error_code="DUPLICATE_NAME")

    data = payload.model_dump(exclude={"details"})
    set_type = SetType(**data)
    db.add(set_type)
    await db.flush()

    for d in payload.details:
        db.add(SetTypeDetail(set_type_id=set_type.id, value=d.value))
    await db.flush()

    result = await db.execute(
        select(SetType).options(selectinload(SetType.details)).where(SetType.id == set_type.id)
    )
    st = result.scalar_one()
    return ResponseModel(
        data=SetTypeResponse.model_validate(st).model_dump(),
        message="Set type created successfully",
    )


@router.get("/{set_type_id}")
async def get_set_type(set_type_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(
        select(SetType).options(selectinload(SetType.details)).where(SetType.id == set_type_id)
    )
    st = result.scalar_one_or_none()
    if not st:
        raise AppException(status_code=404, detail="SetType not found", error_code="NOT_FOUND")
    return ResponseModel(
        data=SetTypeResponse.model_validate(st).model_dump(),
        message="Set type fetched successfully",
    )


@router.patch("/{set_type_id}")
async def update_set_type(
    set_type_id: int,
    payload: SetTypeUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(
        select(SetType).options(selectinload(SetType.details)).where(SetType.id == set_type_id)
    )
    st = result.scalar_one_or_none()
    if not st:
        raise AppException(status_code=404, detail="SetType not found", error_code="NOT_FOUND")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(st, field, value)
    await db.flush()
    await db.refresh(st)
    return ResponseModel(
        data=SetTypeResponse.model_validate(st).model_dump(),
        message="Set type updated successfully",
    )


@router.delete("/{set_type_id}")
async def delete_set_type(set_type_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    st = await db.scalar(select(SetType).where(SetType.id == set_type_id))
    if not st:
        raise AppException(status_code=404, detail="SetType not found", error_code="NOT_FOUND")
    await db.delete(st)
    await db.flush()
    return ResponseModel(data=[], message="Set type deleted successfully")
