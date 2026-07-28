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

    # Travel-allowance daily distance calculation (all tunable via .env)
    TA_GPS_MAX_ACCURACY_M: float = 50.0   # drop pings whose GPS accuracy radius is worse than this
    TA_MIN_SEGMENT_M: float = 30.0        # ignore hops shorter than this (GPS drift while stationary)
    TA_ROAD_FACTOR: float = 1.3           # scale crow-flies distance to approximate real road distance
    TA_EXCLUDE_IN_SHOP: bool = True       # don't count drift accumulated while parked inside a shop

    # Shop-entry geofence
    SHOP_ENTRY_GEOFENCE: bool = True         # validate the executive is near the shop on entry
    SHOP_ENTRY_MAX_DISTANCE_M: float = 200.0 # allowed distance (metres) from the shop's coordinates

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # ← this is the fix


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()