from fastapi import APIRouter

router = APIRouter(
    prefix="/stocks",
    tags=["Stocks"],
)

@router.get("/")
async def list_stocks():
    return {"message": "Stocks endpoint working"}