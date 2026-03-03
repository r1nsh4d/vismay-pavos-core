from fastapi import APIRouter

router = APIRouter(prefix="/categories", tags=["Categories"])

@router.get("/")
def list_categories():
    return {"message": "ok"}