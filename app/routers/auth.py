from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auth import LoginRequest, RefreshRequest
from app.schemas.user import UserCreate
from app.schemas.common import CommonResponse, ErrorResponseModel, ResponseModel
from app.services import auth as auth_mgmt
from app.services.users import serialize_user

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=CommonResponse)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    if auth_mgmt.get_user_by_username_or_email(db, user_in.username, user_in.email):
        return ErrorResponseModel(code=400, message="Username or email already exists", error={})

    user = auth_mgmt.create_user_record(db, user_in)
    return ResponseModel(data=serialize_user(user), message="User registered successfully")


@router.post("/login", response_model=CommonResponse)
def login(login_in: LoginRequest, db: Session = Depends(get_db)):
    user = auth_mgmt.authenticate(db, login_in.login, login_in.password)
    if not user:
        return ErrorResponseModel(code=400, message="Invalid credentials", error={})

    tokens = auth_mgmt.issue_token_pair(db, user.id)
    return ResponseModel(data=tokens, message="Login successful")


@router.post("/refresh", response_model=CommonResponse)
def refresh_token(refresh_in: RefreshRequest, db: Session = Depends(get_db)):
    user_id = auth_mgmt.validate_refresh(db, refresh_in.refresh_token)
    if not user_id:
        return ErrorResponseModel(code=401, message="Refresh token is invalid or expired", error={})

    tokens = auth_mgmt.issue_token_pair(db, user_id)
    return ResponseModel(data=tokens, message="Tokens refreshed successfully")


@router.post("/logout", response_model=CommonResponse)
def logout(refresh_in: RefreshRequest, db: Session = Depends(get_db)):
    user_id = auth_mgmt.validate_refresh(db, refresh_in.refresh_token)
    if not user_id:
        return ErrorResponseModel(code=401, message="Invalid refresh token", error={})

    auth_mgmt.revoke_refresh_token(db, user_id)
    return ResponseModel(data=None, message="Logged out successfully")