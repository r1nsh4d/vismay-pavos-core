from pydantic import BaseModel, EmailStr
from app.schemas.base import CamelModel


class LoginRequest(CamelModel):
    email: EmailStr
    password: str


class TokenResponse(CamelModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(CamelModel):
    refresh_token: str


class AccessTokenResponse(CamelModel):
    access_token: str
    token_type: str = "bearer"
