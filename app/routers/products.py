from fastapi import APIRouter

router = APIRouter(
    prefix="/products",
    tags=["Products"],
)

@router.get("/")
async def list_products():
    return {"message": "Products endpoint working"}