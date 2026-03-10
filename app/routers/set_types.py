import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.common import CommonResponse, ResponseModel, ErrorResponseModel, PaginatedResponse
from app.schemas.set_type import SetTypeCreate, SetTypeUpdate, SetTypeResponse
from app.services import set_types as st_svc

router = APIRouter(prefix="/set-types", tags=["Set Types"])


@router.post("", response_model=CommonResponse)
async def create_set_type(st_in: SetTypeCreate, db: AsyncSession = Depends(get_db)):
    st = await st_svc.create_set_type(db, st_in)
    return ResponseModel(data=SetTypeResponse.model_validate(st), message="Set type created")


@router.get("", response_model=CommonResponse)
async def list_set_types(
    category_id: uuid.UUID | None = None,
    page: int = 1, limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    sts, total = await st_svc.get_all_set_types(db, category_id=category_id, page=page, limit=limit)
    return PaginatedResponse(data=[SetTypeResponse.model_validate(s) for s in sts], message="Set types fetched", page=page, limit=limit, total=total)


@router.get("/{set_type_id}", response_model=CommonResponse)
async def get_set_type(set_type_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    st = await st_svc.get_set_type_by_id(db, set_type_id)
    if not st:
        return ErrorResponseModel(code=404, message="Set type not found", error={})
    return ResponseModel(data=SetTypeResponse.model_validate(st), message="Set type fetched")


@router.put("/{set_type_id}", response_model=CommonResponse)
async def update_set_type(set_type_id: uuid.UUID, st_in: SetTypeUpdate, db: AsyncSession = Depends(get_db)):
    st = await st_svc.get_set_type_by_id(db, set_type_id)
    if not st:
        return ErrorResponseModel(code=404, message="Set type not found", error={})
    st = await st_svc.update_set_type(db, st, st_in)
    return ResponseModel(data=SetTypeResponse.model_validate(st), message="Set type updated")


@router.delete("/{set_type_id}", response_model=CommonResponse)
async def delete_set_type(set_type_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    st = await st_svc.get_set_type_by_id(db, set_type_id)
    if not st:
        return ErrorResponseModel(code=404, message="Set type not found", error={})
    await st_svc.delete_set_type(db, st)
    return ResponseModel(data=None, message="Set type deleted")