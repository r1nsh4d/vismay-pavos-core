import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.common import CommonResponse, ErrorResponseModel, ResponseModel, PaginatedResponse
from app.schemas.state import StateCreate, StateUpdate
from app.services import states as state_svc

router = APIRouter(prefix="/states", tags=["States"])


@router.get("/search", response_model=CommonResponse)
async def search_states(
    q: str | None = Query(default=None),
    is_active: bool | None = None,
    page: int = 1,
    limit: int = 40,
    db: AsyncSession = Depends(get_db),
):
    states, total = await state_svc.search_states(db, q=q, is_active=is_active, page=page, limit=limit)
    return PaginatedResponse(
        data=[state_svc.serialize_state(s) for s in states],
        message="States fetched successfully",
        page=page, limit=limit, total=total,
    )


@router.post("", response_model=CommonResponse)
async def create_state(data: StateCreate, db: AsyncSession = Depends(get_db)):
    state = await state_svc.create_state(db, data)
    return ResponseModel(data=state_svc.serialize_state(state), message="State created successfully")


@router.get("/{state_id}", response_model=CommonResponse)
async def get_state(state_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    state = await state_svc.get_state_by_id(db, state_id)
    if not state:
        return ErrorResponseModel(code=404, message="State not found", error={})
    return ResponseModel(data=state_svc.serialize_state(state), message="State fetched successfully")


@router.put("/{state_id}", response_model=CommonResponse)
async def update_state(state_id: uuid.UUID, data: StateUpdate, db: AsyncSession = Depends(get_db)):
    state = await state_svc.get_state_by_id(db, state_id)
    if not state:
        return ErrorResponseModel(code=404, message="State not found", error={})
    state = await state_svc.update_state(db, state, data)
    return ResponseModel(data=state_svc.serialize_state(state), message="State updated successfully")


@router.patch("/{state_id}/toggle", response_model=CommonResponse)
async def toggle_state(state_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    state = await state_svc.get_state_by_id(db, state_id)
    if not state:
        return ErrorResponseModel(code=404, message="State not found", error={})
    state.is_active = not state.is_active
    return ResponseModel(
        data=state_svc.serialize_state(state),
        message=f"State {'activated' if state.is_active else 'deactivated'} successfully",
    )


@router.delete("/{state_id}", response_model=CommonResponse)
async def delete_state(state_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    state = await state_svc.get_state_by_id(db, state_id)
    if not state:
        return ErrorResponseModel(code=404, message="State not found", error={})
    await state_svc.delete_state(db, state)
    return ResponseModel(data=None, message="State deleted successfully")