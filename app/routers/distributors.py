import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_roles
from app.schemas.common import CommonResponse, PaginatedResponse
from app.services import users as user_mgmt

# Read-only distributor lookup. Distributors are users with the `distributor` role;
# executives need this to pick a distributor, without access to the admin-only users router.
router = APIRouter(
    prefix="/distributors", tags=["Distributors"],
    dependencies=[Depends(require_roles("super_admin", "admin", "scm_user", "executive"))]
)


@router.get("/search", response_model=CommonResponse)
async def search_distributors(
    q: str | None = Query(default=None, description="Search by username or email"),
    tenant_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    distributors, total = await user_mgmt.get_distributors(
        db, q=q, tenant_id=tenant_id, is_active=is_active, page=page, limit=limit
    )
    return PaginatedResponse(
        data=[user_mgmt.serialize_user(u) for u in distributors],
        message="Distributors fetched", page=page, limit=limit, total=total,
    )
