import uuid
from typing import List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.database import get_db
from app.dependencies import require_roles
from app.schemas.common import CommonResponse, ResponseModel, PaginatedResponse
from app.schemas.taluk import TalukCreate, TalukUpdate
from app.services import taluk as taluk_mgmt

router = APIRouter(
    prefix="/taluks", tags=["Taluks"],
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
async def search_taluks(
    q: str | None = Query(default=None),
    district_ids: str | None = Query(default=None, description="Comma-separated district UUIDs"),
    is_active: bool | None = None,
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    taluks, total = await taluk_mgmt.get_all_taluks(
        db, q=q, district_ids=_parse_uuids(district_ids), is_active=is_active, page=page, limit=limit
    )
    return PaginatedResponse(
        data=[taluk_mgmt.serialize_taluk(t) for t in taluks],
        message="Taluks fetched", page=page, limit=limit, total=total,
    )


@router.post("", response_model=CommonResponse)
async def create_taluk(data: TalukCreate, db: AsyncSession = Depends(get_db)):
    taluk = await taluk_mgmt.create_taluk(db, data)
    return ResponseModel(data=taluk_mgmt.serialize_taluk(taluk), message="Taluk created")


@router.get("/{taluk_id}", response_model=CommonResponse)
async def get_taluk(taluk_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    taluk = await taluk_mgmt.get_taluk_by_id(db, taluk_id)
    if not taluk:
        raise AppException(status_code=404, detail="Taluk not found")
    return ResponseModel(data=taluk_mgmt.serialize_taluk(taluk), message="Taluk fetched")


@router.put("/{taluk_id}", response_model=CommonResponse)
async def update_taluk(taluk_id: uuid.UUID, data: TalukUpdate, db: AsyncSession = Depends(get_db)):
    taluk = await taluk_mgmt.get_taluk_by_id(db, taluk_id)
    if not taluk:
        raise AppException(status_code=404, detail="Taluk not found")
    taluk = await taluk_mgmt.update_taluk(db, taluk, data)
    return ResponseModel(data=taluk_mgmt.serialize_taluk(taluk), message="Taluk updated")


@router.patch("/{taluk_id}/toggle", response_model=CommonResponse)
async def toggle_taluk(taluk_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    taluk = await taluk_mgmt.get_taluk_by_id(db, taluk_id)
    if not taluk:
        raise AppException(status_code=404, detail="Taluk not found")
    taluk.is_active = not taluk.is_active
    return ResponseModel(
        data=taluk_mgmt.serialize_taluk(taluk),
        message=f"Taluk {'activated' if taluk.is_active else 'deactivated'} successfully",
    )


@router.delete("/{taluk_id}", response_model=CommonResponse)
async def delete_taluk(taluk_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    taluk = await taluk_mgmt.get_taluk_by_id(db, taluk_id)
    if not taluk:
        raise AppException(status_code=404, detail="Taluk not found")
    await taluk_mgmt.delete_taluk(db, taluk)
    return ResponseModel(data=None, message="Taluk deleted")