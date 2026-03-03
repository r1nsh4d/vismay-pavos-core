from fastapi import APIRouter

router = APIRouter(
    prefix="/shops",
    tags=["Shops"],
)

@router.get("/")
async def list_shops():
    return {"message": "Shops endpoint working"}