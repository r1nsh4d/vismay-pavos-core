from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.auth import LoginRequest, RefreshRequest
from app.schemas.user import UserCreate
from app.schemas.common import CommonResponse, ErrorResponseModel, ResponseModel
from app.services import auth as auth_mgmt
from app.services import users as user_mgmt
from app.services.users import serialize_user

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=CommonResponse)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    if await auth_mgmt.get_user_by_username_or_email(db, user_in.username, user_in.email):
        return ErrorResponseModel(code=400, message="Username or email already exists", error={})

    user = await auth_mgmt.create_user_record(db, user_in)
    return ResponseModel(data=serialize_user(user), message="User registered successfully")


@router.post("/login", response_model=CommonResponse)
async def login(login_in: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await auth_mgmt.authenticate(db, login_in.login, login_in.password)
    if not user:
        return ErrorResponseModel(code=400, message="Invalid credentials", error={})

    tokens = await auth_mgmt.issue_token_pair(db, user.id)
    return ResponseModel(data=tokens, message="Login successful")


@router.post("/refresh", response_model=CommonResponse)
async def refresh_token(refresh_in: RefreshRequest, db: AsyncSession = Depends(get_db)):
    user_id = await auth_mgmt.validate_refresh(db, refresh_in.refresh_token)
    if not user_id:
        return ErrorResponseModel(code=401, message="Refresh token is invalid or expired", error={})

    tokens = await auth_mgmt.issue_token_pair(db, user_id)
    return ResponseModel(data=tokens, message="Tokens refreshed successfully")


@router.post("/logout", response_model=CommonResponse)
async def logout(refresh_in: RefreshRequest, db: AsyncSession = Depends(get_db)):
    user_id = await auth_mgmt.validate_refresh(db, refresh_in.refresh_token)
    if not user_id:
        return ErrorResponseModel(code=401, message="Invalid refresh token", error={})

    await auth_mgmt.revoke_refresh_token(db, user_id)
    return ResponseModel(data=None, message="Logged out successfully")


@router.get("/me", response_model=CommonResponse)
async def get_me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = await user_mgmt.get_user_by_id(db, current_user.id)
    return ResponseModel(data=user_mgmt.serialize_user(user), message="Profile fetched successfully")