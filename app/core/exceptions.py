from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


# ─── AppException ─────────────────────────────────────────────────────────────

class AppException(Exception):
    def __init__(self, status_code: int, detail: str, error_code: str = None):
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code or f"ERROR_{status_code}"
        self.data = None


# ─── Base error response ──────────────────────────────────────────────────────

def _error_response(
    status_code: int,
    message: str,
    errors: list = None,
    error_code: str = None,
) -> JSONResponse:
    content = {
        "success": False,
        "message": message,
        "errors": errors if errors is not None else [],
        "data": None
    }
    if error_code:
        content["error_code"] = error_code

    return JSONResponse(status_code=status_code, content=content)


# ─── Handlers ─────────────────────────────────────────────────────────────────

async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return _error_response(
        status_code=exc.status_code,
        message=exc.detail,
        error_code=exc.error_code,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return _error_response(
        status_code=exc.status_code,
        message=str(exc.detail),
        error_code=f"HTTP_{exc.status_code}",
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = []
    for e in exc.errors():
        loc = [str(l) for l in e["loc"] if l not in ("body", "query", "path", "header")]
        field = " -> ".join(loc) if loc else "unknown"

        msg = e["msg"]
        msg = msg.replace("Value error, ", "")
        msg = msg.replace("String should have at least", "Minimum length is")
        msg = msg.replace("value is not a valid email address", "Invalid email address")
        msg = msg.replace("field required", "This field is required")

        errors.append({"field": field, "message": msg})

    return _error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        message="Validation failed",
        errors=errors,
        error_code="VALIDATION_ERROR",
    )


async def internal_server_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return _error_response(
        status_code=500,
        message="Internal server error",
        error_code="INTERNAL_SERVER_ERROR",
    )


# ─── Register all handlers ────────────────────────────────────────────────────

def register_exception_handlers(app):
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, internal_server_error_handler)