# ─── Auth ─────────────────────────────────────────────────────────────────────
from app.schemas.base import CamelModel


class LoginRequest(CamelModel):
    login: str          # accepts email or username
    password: str


class RefreshRequest(CamelModel):
    refresh_token: str


class TokenResponse(CamelModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
