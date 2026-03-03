from fastapi import APIRouter

router = APIRouter(
    prefix="/set-types",
    tags=["Set Types"],
)

@router.get("/")
async def list_set_types():
    return {"message": "ok"}