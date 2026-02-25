from typing import Any, Optional
from pydantic import BaseModel, ConfigDict


def to_camel(string: str) -> str:
    parts = string.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


def camelize(data: Any) -> Any:
    """
    Recursively convert dictionary keys to camelCase
    """
    if isinstance(data, list):
        return [camelize(item) for item in data]
    elif isinstance(data, dict):
        return {to_camel(key): camelize(value) for key, value in data.items()}
    else:
        return data


class CommonResponse(BaseModel):
    status: str = "failure"
    message: str = "API failed"
    data: Optional[Any] = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class ErrorResponse(BaseModel):
    status: str = "failure"
    error_code: int
    message: str
    error: Optional[Any] = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


def ResponseModel(data: Any, message: str) -> CommonResponse:
    return CommonResponse(
        status="success",
        message=message,
        data=camelize(data),  # 🔥 convert here
    )


def ErrorResponseModel(error: Any, code: int, message: str) -> ErrorResponse:
    return ErrorResponse(
        status="failure",
        error_code=code,
        message=message,
        error=camelize(error),
    )