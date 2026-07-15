from app.schemas.base import CamelModel


# Auth
class LoginRequest(CamelModel):
    login: str
    password: str
    app_version_code: int | None = None   # sent by Android app only, omitted by web
    client_type: str | None = None        # "android" | omitted for web


class RefreshRequest(CamelModel):
    refresh_token: str


class TokenResponse(CamelModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"