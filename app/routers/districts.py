import uuid
from typing import List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.database import get_db
from app.dependencies import require_roles
from app.schemas.common import CommonResponse, ErrorResponseModel, ResponseModel, PaginatedResponse
from app.schemas.district import DistrictCreate, DistrictUpdate, DistrictResponse
from app.services import districts as district_mgmt

router = APIRouter(
    prefix="/districts", tags=["Districts"],
    dependencies=[Depends(require_roles("super_admin", "admin", "scm_user"))]
)


def _parse_uuids(val: str | None) -> List[uuid.UUID]:
    if not val:
        return []
    try:
        return [uuid.UUID(v.strip()) for v in val.split(",") if v.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID in query parameter")


@router.get("/search", response_model=CommonResponse)
async def search_districts(
    q: str | None = Query(default=None),
    state_ids: str | None = Query(default=None, description="Comma-separated state UUIDs"),
    is_active: bool | None = None,
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    districts, total = await district_mgmt.get_all_districts(
        db, q=q, state_ids=_parse_uuids(state_ids), is_active=is_active, page=page, limit=limit
    )
    return PaginatedResponse(
        data=[district_mgmt.serialize_district(d) for d in districts],
        message="Districts fetched", page=page, limit=limit, total=total,
    )


@router.post("", response_model=CommonResponse)
async def create_district(data: DistrictCreate, db: AsyncSession = Depends(get_db)):
    district = await district_mgmt.create_district(db, data)
    return ResponseModel(data=district_mgmt.serialize_district(district), message="District created")


@router.get("/{district_id}", response_model=CommonResponse)
async def get_district(district_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    district = await district_mgmt.get_district_by_id(db, district_id)
    if not district:
        raise AppException(status_code=404, detail="District not found")
    return ResponseModel(data=district_mgmt.serialize_district(district), message="District fetched")


@router.put("/{district_id}", response_model=CommonResponse)
async def update_district(district_id: uuid.UUID, data: DistrictUpdate, db: AsyncSession = Depends(get_db)):
    district = await district_mgmt.get_district_by_id(db, district_id)
    if not district:
        raise AppException(status_code=404, detail="District not found")
    district = await district_mgmt.update_district(db, district, data)
    return ResponseModel(data=district_mgmt.serialize_district(district), message="District updated")


@router.patch("/{district_id}/toggle", response_model=CommonResponse)
async def toggle_district(district_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    district = await district_mgmt.get_district_by_id(db, district_id)
    if not district:
        raise AppException(status_code=404, detail="District not found")
    district.is_active = not district.is_active
    return ResponseModel(
        data=district_mgmt.serialize_district(district),
        message=f"District {'activated' if district.is_active else 'deactivated'} successfully",
    )


@router.delete("/{district_id}", response_model=CommonResponse)
async def delete_district(district_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    district = await district_mgmt.get_district_by_id(db, district_id)
    if not district:
        raise AppException(status_code=404, detail="District not found")
    await district_mgmt.delete_district(db, district)
    return ResponseModel(data=None, message="District deleted")