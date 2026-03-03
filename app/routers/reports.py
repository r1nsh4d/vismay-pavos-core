from fastapi import APIRouter

router = APIRouter(
    prefix="/reports",
    tags=["Reports"],
)

@router.get("/")
async def list_reports():
    return {"message": "Reports endpoint working"}

@router.get("/sales")
async def sales_report():
    return {"message": "Sales report data"}

@router.get("/inventory")
async def inventory_report():
    return {"message": "Inventory report data"}