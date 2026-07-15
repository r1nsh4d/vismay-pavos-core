from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.database import get_db
from app.dependencies import require_roles
from app.models.app_version import AppVersion
from app.schemas.app_version import AppVersionOut, VersionCheckIn, VersionCheckOut
from app.schemas.common import CommonResponse, ResponseModel
from app.services.storage_service import upload_apk

router = APIRouter(prefix="/app-version", tags=["App Version"])


async def _get_latest_active(db: AsyncSession) -> AppVersion | None:
    result = await db.execute(
        select(AppVersion)
        .where(AppVersion.is_active.is_(True))
        .order_by(AppVersion.version_code.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@router.post("", response_model=CommonResponse, dependencies=[Depends(require_roles("super_admin", "admin"))])
async def upload_new_version(
    version_code: int = Form(...),
    version_name: str = Form(...),
    min_required_version_code: int = Form(...),
    release_notes: str | None = Form(None),
    apk_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    if not apk_file.filename.endswith(".apk"):
        raise AppException(status_code=400, detail="File must be an .apk")

    file_bytes = await apk_file.read()
    apk_key, apk_url = await upload_apk(file_bytes, version_code)

    new_version = AppVersion(
        version_code=version_code,
        version_name=version_name,
        min_required_version_code=min_required_version_code,
        apk_key=apk_key,
        apk_url=apk_url,
        release_notes=release_notes,
    )
    db.add(new_version)
    await db.commit()
    await db.refresh(new_version)

    return ResponseModel(data=AppVersionOut.model_validate(new_version), message="Version uploaded")


@router.get("/latest", response_model=CommonResponse)
async def get_latest_version(db: AsyncSession = Depends(get_db)):
    latest = await _get_latest_active(db)
    if not latest:
        raise AppException(status_code=404, detail="No active version found")
    return ResponseModel(data=AppVersionOut.model_validate(latest), message="Latest version")


@router.post("/check", response_model=CommonResponse)
async def check_version(payload: VersionCheckIn, db: AsyncSession = Depends(get_db)):
    latest = await _get_latest_active(db)
    if not latest:
        raise AppException(status_code=404, detail="No active version found")

    force_update = payload.version_code < latest.min_required_version_code

    return ResponseModel(
        data=VersionCheckOut(
            force_update=force_update,
            latest_version_code=latest.version_code,
            latest_version_name=latest.version_name,
            apk_url=latest.apk_url,
            release_notes=latest.release_notes,
        ),
        message="Version check complete",
    )
