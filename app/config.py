from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "vismay-pavos-core"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./dev.db"

    # JWT
    SECRET_KEY: str = "secret1"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Hetzner Object Storage
    HETZNER_ACCESS_KEY: str = ""
    HETZNER_SECRET_KEY: str = ""
    HETZNER_BUCKET_NAME: str = "vismay-pavos-products"
    HETZNER_ENDPOINT_URL: str = ""  # e.g. https://fsn1.your-objectstorage.com
    HETZNER_PUBLIC_BASE_URL: str = ""  # e.g. https://vismay-pavis-products.fsn1.your-objectstorage.com

    # Image upload settings
    IMAGE_MAX_FILE_SIZE_MB: int = 5
    IMAGE_MIN_DIMENSION: int = 400
    IMAGE_QUALITY: int = 90
    IMAGE_THUMBNAIL_QUALITY: int = 78
    IMAGE_THUMBNAIL_SIZE: int = 300  # square — used as (N, N)

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # ← this is the fix


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()