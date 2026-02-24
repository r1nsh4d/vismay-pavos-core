from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.security import hash_password
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import ResponseModel
from app.schemas.user import UserCreate, UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    offset = (page - 1) * page_size
    query = select(User)
    count_query = select(func.count()).select_from(User)
    if tenant_id:
        query = query.where(User.tenant_id == tenant_id)
        count_query = count_query.where(User.tenant_id == tenant_id)
    total = await db.scalar(count_query)
    result = await db.execute(query.offset(offset).limit(page_size))
    users = [UserResponse.model_validate(u).model_dump() for u in result.scalars().all()]
    return ResponseModel(
        data={"total": total, "page": page, "page_size": page_size, "results": users},
        message="Users fetched successfully",
    )


@router.post("", status_code=201)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise AppException(status_code=409, detail="Email already registered", error_code="DUPLICATE_EMAIL")

    data = payload.model_dump(exclude={"password"})
    data["password_hash"] = hash_password(payload.password)
    user = User(**data)
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return ResponseModel(
        data=UserResponse.model_validate(user).model_dump(),
        message="User created successfully",
    )


@router.get("/{user_id}")
async def get_user(user_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise AppException(status_code=404, detail="User not found", error_code="NOT_FOUND")
    return ResponseModel(
        data=UserResponse.model_validate(user).model_dump(),
        message="User fetched successfully",
    )


@router.patch("/{user_id}")
async def update_user(
    user_id: int,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise AppException(status_code=404, detail="User not found", error_code="NOT_FOUND")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.flush()
    await db.refresh(user)
    return ResponseModel(
        data=UserResponse.model_validate(user).model_dump(),
        message="User updated successfully",
    )


@router.delete("/{user_id}")
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise AppException(status_code=404, detail="User not found", error_code="NOT_FOUND")
    await db.delete(user)
    await db.flush()
    return ResponseModel(data=[], message="User deleted successfully")
