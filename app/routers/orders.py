from fastapi import APIRouter

router = APIRouter(
    prefix="/orders",
    tags=["Orders"],
)

@router.get("/")
async def list_orders():
    return {"message": "Orders endpoint working"}

@router.get("/{order_id}")
async def get_order(order_id: int):
    return {"order_id": order_id}

@router.post("/")
async def create_order():
    return {"message": "Order created"}