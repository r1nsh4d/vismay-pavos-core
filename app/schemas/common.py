from math import ceil
from typing import Any, Optional

from app.schemas.base import CamelModel


class CommonResponse(CamelModel):
    success: bool = True
    message: str = "Success"
    data: Optional[Any] = None
    meta: Optional[Any] = None


class ErrorResponse(CamelModel):
    success: bool = False
    status: str = "failure"
    errorCode: int          # camelCase alias
    message: str
    error: Optional[Any] = None


def ResponseModel(data: Any, message: str = "Success") -> CommonResponse:
    return CommonResponse(
        success=True,
        message=message,
        data=data,
    )


def ErrorResponseModel(code: int, message: str, error: dict):
    print(f"{code}|{message}|{error}")
    return ErrorResponse(
        success=False,
        status='failure',
        errorCode=code,  # was error_code
        message=message,
        error=error,
    )


def PaginatedResponse(
    data: list,
    message: str = "Success",
    page: int = 1,
    limit: int = 20,
    total: int = 0,
) -> CommonResponse:
    return CommonResponse(
        success=True,
        message=message,
        data=data,
        meta={
            "page": page,
            "limit": limit,
            "total": total,
            "totalPages": ceil(total / limit) if limit > 0 else 0,
        },
    )