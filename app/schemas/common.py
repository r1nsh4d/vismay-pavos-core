import uuid
import math
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict


def to_camel(string: str) -> str:
    parts = string.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


def camelize(data: Any) -> Any:
    """
    Recursively convert dictionary keys to camelCase.
    Handles UUID objects by converting them to strings.
    """
    if isinstance(data, list):
        return [camelize(item) for item in data]
    elif isinstance(data, dict):
        return {to_camel(key): camelize(value) for key, value in data.items()}
    elif isinstance(data, uuid.UUID):
        return str(data)  # 🔥 Ensure UUIDs become strings for the JSON
    else:
        return data


class CommonResponse(BaseModel):
    success: bool = True
    message: str = "Success"
    data: Optional[Any] = None
    meta: Optional[Any] = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        # Allows Pydantic to handle non-dict data like SQLAlchemy models
        from_attributes=True 
    )


class ErrorResponse(BaseModel):
    status: str = "failure"
    error_code: int
    message: str
    error: Optional[Any] = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True
    )


def ResponseModel(data: Any, message: str) -> CommonResponse:
    # Changed status to success to match the field name in CommonResponse
    return CommonResponse(
        success=True,
        message=message,
        data=camelize(data),
    )


def ErrorResponseModel(error: Any, code: int, message: str) -> ErrorResponse:
    return ErrorResponse(
        status="failure",
        error_code=code,
        message=message,
        error=camelize(error),
    )


def PaginatedResponse(data: list, message: str, page: int, limit: int, total: int) -> CommonResponse:
    return CommonResponse(
        success=True,
        message=message,
        data=camelize(data),
        meta={
            "page": page,
            "limit": limit,
            "total": total,
            "totalPages": math.ceil(total / limit) if limit > 0 else 0,
        },
    )