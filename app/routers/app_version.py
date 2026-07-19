from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.database import get_db
from app.dependencies import require_roles
from app.models.app_version import AppVersion
from app.schemas.app_version import AppVersionOut, VersionCheckIn
from app.schemas.common import CommonResponse, ResponseModel
from app.services.storage_service import upload_apk

router = APIRouter(prefix="/app-version", tags=["App Version"])


def _parse_version(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(p) for p in v.strip().split("."))
    except (ValueError, AttributeError):
        return ()


def _version_lt(a: str, b: str) -> bool:
    """True if semantic version `a` is lower than `b` (e.g. "2.1.0" < "2.3.0")."""
    pa, pb = _parse_version(a), _parse_version(b)
    length = max(len(pa), len(pb))
    pa += (0,) * (length - len(pa))
    pb += (0,) * (length - len(pb))
    return pa < pb


def _build_out(v: AppVersion, force_update: bool | None = None) -> AppVersionOut:
    return AppVersionOut(
        latest_version=v.version,
        min_supported_version=v.min_supported_version,
        force_update=v.force_update if force_update is None else force_update,
        download_url=v.apk_url,
        release_date=v.created_at,
        release_notes=v.release_notes or [],
    )


async def _get_latest_active(db: AsyncSession) -> AppVersion | None:
    result = await db.execute(
        select(AppVersion)
        .where(AppVersion.is_active.is_(True))
        .order_by(AppVersion.created_at.desc(), AppVersion.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@router.post("", response_model=CommonResponse, dependencies=[Depends(require_roles("super_admin", "admin"))])
async def upload_new_version(
    version: str = Form(...),
    min_supported_version: str = Form(...),
    force_update: bool = Form(False),
    release_notes: list[str] = Form([]),
    apk_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    if not apk_file.filename.endswith(".apk"):
        raise AppException(status_code=400, detail="File must be an .apk")

    file_bytes = await apk_file.read()
    apk_key, apk_url = await upload_apk(file_bytes, version)

    new_version = AppVersion(
        version=version,
        min_supported_version=min_supported_version,
        force_update=force_update,
        apk_key=apk_key,
        apk_url=apk_url,
        release_notes=release_notes,
    )
    db.add(new_version)
    await db.commit()
    await db.refresh(new_version)

    return ResponseModel(data=_build_out(new_version), message="Version uploaded")


@router.get("/latest", response_model=CommonResponse)
async def get_latest_version(db: AsyncSession = Depends(get_db)):
    latest = await _get_latest_active(db)
    if not latest:
        raise AppException(status_code=404, detail="No active version found")
    return ResponseModel(data=_build_out(latest), message="Latest version")


@router.post("/check", response_model=CommonResponse)
async def check_version(payload: VersionCheckIn, db: AsyncSession = Depends(get_db)):
    latest = await _get_latest_active(db)
    if not latest:
        raise AppException(status_code=404, detail="No active version found")

    # Force the update if the release is flagged mandatory, or the client is below the supported floor.
    force = latest.force_update or _version_lt(payload.version, latest.min_supported_version)

    return ResponseModel(data=_build_out(latest, force_update=force), message="Version check complete")
