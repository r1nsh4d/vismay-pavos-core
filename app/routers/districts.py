from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid

from app.database import get_db
from app.schemas.common import CommonResponse, ErrorResponseModel, ResponseModel
from app.schemas.district import DistrictCreate, DistrictResponse
from app.services import districts as district_svc

router = APIRouter(prefix="/districts", tags=["Districts"])


@router.post("", response_model=CommonResponse)
def create_district(dist_in: DistrictCreate, db: Session = Depends(get_db)):
    dist = district_svc.create_district(db, dist_in)
    return ResponseModel(data=DistrictResponse.model_validate(dist), message="District created")


@router.get("", response_model=CommonResponse)
def list_districts(state: str | None = None, db: Session = Depends(get_db)):
    districts = district_svc.get_all_districts(db, state=state)
    return ResponseModel(data=[DistrictResponse.model_validate(d) for d in districts], message="Districts fetched")


@router.get("/{district_id}", response_model=CommonResponse)
def get_district(district_id: uuid.UUID, db: Session = Depends(get_db)):
    dist = district_svc.get_district_by_id(db, district_id)
    if not dist:
        return ErrorResponseModel(code=404, message="District not found", error={})
    return ResponseModel(data=DistrictResponse.model_validate(dist), message="District fetched")


@router.put("/{district_id}", response_model=CommonResponse)
def update_district(district_id: uuid.UUID, dist_in: DistrictCreate, db: Session = Depends(get_db)):
    dist = district_svc.get_district_by_id(db, district_id)
    if not dist:
        return ErrorResponseModel(code=404, message="District not found", error={})

    dist = district_svc.update_district(db, dist, dist_in)
    return ResponseModel(data=DistrictResponse.model_validate(dist), message="District updated")


@router.delete("/{district_id}", response_model=CommonResponse)
def delete_district(district_id: uuid.UUID, db: Session = Depends(get_db)):
    dist = district_svc.get_district_by_id(db, district_id)
    if not dist:
        return ErrorResponseModel(code=404, message="District not found", error={})

    district_svc.delete_district(db, dist)
    return ResponseModel(data=None, message="District deleted")