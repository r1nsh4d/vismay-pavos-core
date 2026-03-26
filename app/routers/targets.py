import uuid
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.common import CommonResponse, ResponseModel, ErrorResponseModel
from app.schemas.target import TargetCreate, TargetResponse
from app.services import targets as target_svc
from app.models.user import User

router = APIRouter(prefix="/targets", tags=["Targets"])


@router.post("", response_model=CommonResponse)
async def set_target(
    target_in: TargetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin/SCM sets monthly target for an executive."""
    target = await target_svc.set_target(db, target_in)
    await db.commit()
    return ResponseModel(
        data=TargetResponse.model_validate(target).model_dump(by_alias=True),
        message="Target set successfully",
    )


@router.get("/{user_id}", response_model=CommonResponse)
async def get_targets(
    user_id: uuid.UUID,
    year: int | None = None,
    month: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all targets for an executive for a given month."""
    now = datetime.utcnow()
    targets = await target_svc.get_targets_by_user(
        db, user_id=user_id,
        year=year or now.year,
        month=month or now.month,
    )
    return ResponseModel(
        data=[TargetResponse.model_validate(t).model_dump(by_alias=True) for t in targets],
        message="Targets fetched",
    )


@router.get("/{user_id}/achievement", response_model=CommonResponse)
async def get_achievement(
    user_id: uuid.UUID,
    year: int | None = None,
    month: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get achievement summary vs targets for an executive."""
    now = datetime.utcnow()
    summary = await target_svc.get_achievement_summary(
        db, user_id=user_id,
        year=year or now.year,
        month=month or now.month,
    )
    return ResponseModel(data=summary, message="Achievement fetched")


@router.get("/my/achievement", response_model=CommonResponse)
async def get_my_achievement(
    year: int | None = None,
    month: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Executive checks their own achievement."""
    now = datetime.utcnow()
    summary = await target_svc.get_achievement_summary(
        db, user_id=current_user.id,
        year=year or now.year,
        month=month or now.month,
    )
    return ResponseModel(data=summary, message="My achievement fetched")


@router.delete("/{user_id}/{target_id}", response_model=CommonResponse)
async def delete_target(
    user_id: uuid.UUID,
    target_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = await target_svc.delete_target(db, user_id=user_id, target_id=target_id)
    if not deleted:
        return ErrorResponseModel(code=404, message="Target not found", error={})
    await db.commit()
    return ResponseModel(data=None, message="Target deleted")