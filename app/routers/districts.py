<<<<<<< Updated upstream
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.database import get_db
from app.dependencies import get_current_user
from app.models.district import District
from app.schemas.common import ResponseModel, PaginatedResponse
from app.schemas.district import DistrictCreate, DistrictResponse, DistrictUpdate

router = APIRouter(prefix="/districts", tags=["Districts"])


@router.get("")
async def list_districts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    offset = (page - 1) * limit
    total = await db.scalar(select(func.count()).select_from(District))
    result = await db.execute(select(District).offset(offset).limit(limit))
    districts = [DistrictResponse.model_validate(d).model_dump() for d in result.scalars().all()]
    return PaginatedResponse(
        data=districts,
        message="Districts fetched successfully",
        limit=limit,
        page=page,
        total=total
    )


@router.post("", status_code=201)
async def create_district(
    payload: DistrictCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    district = District(**payload.model_dump())
    db.add(district)
    await db.flush()
    await db.refresh(district)
    return ResponseModel(
        data=DistrictResponse.model_validate(district).model_dump(),
        message="District created successfully",
    )


@router.get("/{district_id}")
async def get_district(district_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(District).where(District.id == district_id))
    district = result.scalar_one_or_none()
    if not district:
        raise AppException(status_code=404, detail="District not found", error_code="NOT_FOUND")
    return ResponseModel(
        data=DistrictResponse.model_validate(district).model_dump(),
        message="District fetched successfully",
    )


@router.patch("/{district_id}")
async def update_district(
    district_id: int,
    payload: DistrictUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(select(District).where(District.id == district_id))
    district = result.scalar_one_or_none()
    if not district:
        raise AppException(status_code=404, detail="District not found", error_code="NOT_FOUND")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(district, field, value)
    await db.flush()
    await db.refresh(district)
    return ResponseModel(
        data=DistrictResponse.model_validate(district).model_dump(),
        message="District updated successfully",
    )


@router.delete("/{district_id}")
async def delete_district(district_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(District).where(District.id == district_id))
    district = result.scalar_one_or_none()
    if not district:
        raise AppException(status_code=404, detail="District not found", error_code="NOT_FOUND")
    await db.delete(district)
    await db.flush()
    return ResponseModel(data=[], message="District deleted successfully")
=======
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.database import get_db
from app.dependencies import get_current_user
from app.models.district import District
from app.schemas.common import ResponseModel, PaginatedResponse
from app.schemas.district import DistrictCreate, DistrictResponse, DistrictUpdate

router = APIRouter(prefix="/districts", tags=["Districts"])


@router.get("")
async def list_districts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    offset = (page - 1) * limit
    total = await db.scalar(select(func.count()).select_from(District))
    result = await db.execute(select(District).offset(offset).limit(limit))
    districts = [DistrictResponse.model_validate(d).model_dump() for d in result.scalars().all()]
    return PaginatedResponse(
        data=districts,
        message="Districts fetched successfully",
        limit=limit,
        page=page,
        total=total
    )


@router.post("", status_code=201)
async def create_district(
    payload: DistrictCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    district = District(**payload.model_dump())
    db.add(district)
    await db.flush()
    await db.refresh(district)
    return ResponseModel(
        data=DistrictResponse.model_validate(district).model_dump(),
        message="District created successfully",
    )


@router.get("/{district_id}")
async def get_district(district_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(District).where(District.id == district_id))
    district = result.scalar_one_or_none()
    if not district:
        raise AppException(status_code=404, detail="District not found", error_code="NOT_FOUND")
    return ResponseModel(
        data=DistrictResponse.model_validate(district).model_dump(),
        message="District fetched successfully",
    )


@router.patch("/{district_id}")
async def update_district(
    district_id: int,
    payload: DistrictUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(select(District).where(District.id == district_id))
    district = result.scalar_one_or_none()
    if not district:
        raise AppException(status_code=404, detail="District not found", error_code="NOT_FOUND")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(district, field, value)
    await db.flush()
    await db.refresh(district)
    return ResponseModel(
        data=DistrictResponse.model_validate(district).model_dump(),
        message="District updated successfully",
    )


@router.delete("/{district_id}")
async def delete_district(district_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(District).where(District.id == district_id))
    district = result.scalar_one_or_none()
    if not district:
        raise AppException(status_code=404, detail="District not found", error_code="NOT_FOUND")
    await db.delete(district)
    await db.flush()
    return ResponseModel(data=[], message="District deleted successfully")
>>>>>>> Stashed changes
