from typing import Any
from pydantic import BaseModel


class CommonResponse(BaseModel):
    status: str = "failure"
    message: str = "API failed"
    data: Any = []

    class Config:
        json_schema_extra = {
            "example": {"status": "failure", "message": "API failed", "data": None}
        }


def ResponseModel(data: Any, message: str) -> dict:
    return {
        "status": "success",
        "message": message,
        "data": data,
    }


def ErrorResponseModel(error: Any, code: int, message: str) -> dict:
    return {
        "status": "failure",
        "error": error,
        "code": code,
        "message": message,
    }
