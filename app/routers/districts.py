from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.database import get_db
from app.dependencies import require_roles
from app.schemas.common import CommonResponse, ErrorResponseModel, ResponseModel, PaginatedResponse
from app.schemas.district import DistrictCreate, DistrictResponse
from app.services import districts as district_mgmt

router = APIRouter(prefix="/districts", tags=["Districts"], dependencies=[Depends(require_roles("super_admin", "admin"))])


@router.post("", response_model=CommonResponse)
async def create_district(dist_in: DistrictCreate, db: AsyncSession = Depends(get_db)):
    dist = await district_mgmt.create_district(db, dist_in)
    return ResponseModel(data=DistrictResponse.model_validate(dist), message="District created")


@router.get("", response_model=CommonResponse)
async def list_districts(
    state: str | None = None,
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    districts, total = await district_mgmt.get_all_districts(db, state=state, page=page, limit=limit)
    return PaginatedResponse(
        data=[DistrictResponse.model_validate(d) for d in districts],
        message="Districts fetched",
        page=page,
        limit=limit,
        total=total,
    )

@router.get("/{district_id}", response_model=CommonResponse)
async def get_district(district_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    dist = await district_mgmt.get_district_by_id(db, district_id)
    if not dist:
        return ErrorResponseModel(code=404, message="District not found", error={})
    return ResponseModel(data=DistrictResponse.model_validate(dist), message="District fetched")


@router.put("/{district_id}", response_model=CommonResponse)
async def update_district(district_id: uuid.UUID, dist_in: DistrictCreate, db: AsyncSession = Depends(get_db)):
    dist = await district_mgmt.get_district_by_id(db, district_id)
    if not dist:
        return ErrorResponseModel(code=404, message="District not found", error={})

    dist = await district_mgmt.update_district(db, dist, dist_in)
    return ResponseModel(data=DistrictResponse.model_validate(dist), message="District updated")


@router.delete("/{district_id}", response_model=CommonResponse)
async def delete_district(district_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    dist = await district_mgmt.get_district_by_id(db, district_id)
    if not dist:
        return ErrorResponseModel(code=404, message="District not found", error={})

    await district_mgmt.delete_district(db, dist)
    return ResponseModel(data=None, message="District deleted")