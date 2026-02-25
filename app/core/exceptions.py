from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppException(Exception):
    def __init__(self, status_code: int, detail: str, error_code: str = None):
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code or f"ERROR_{status_code}"


def _error_response(status_code: int, message: str, data=None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "failure",
            "message": message,
            "data": data if data is not None else [],
        },
    )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return _error_response(exc.status_code, exc.detail)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return _error_response(exc.status_code, str(exc.detail))


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"field": " -> ".join(str(l) for l in e["loc"]), "message": e["msg"]}
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "failure",
            "message": "Validation error",
            "data": errors,
        },
    )


async def internal_server_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return _error_response(500, "Internal server error")
