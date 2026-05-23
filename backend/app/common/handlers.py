"""全局异常处理器。"""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.common.exceptions import AppError


def _cors_headers(request: Request) -> dict[str, str]:
    origin = request.headers.get("origin")
    if origin and origin in get_settings().cors_origin_list:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }
    return {}


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", None)
    detail = exc.errors()[0].get("msg", "参数校验失败") if exc.errors() else "参数校验失败"
    return JSONResponse(
        status_code=422,
        headers=_cors_headers(request),
        content={
            "code": 422,
            "message": detail,
            "data": None,
            "trace_id": trace_id,
        },
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        headers=_cors_headers(request),
        content={
            "code": exc.code,
            "message": exc.message,
            "data": None,
            "trace_id": trace_id,
        },
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    settings = get_settings()
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse(
        status_code=500,
        headers=_cors_headers(request),
        content={
            "code": 500,
            "message": str(exc) if settings.debug else "服务器内部错误",
            "data": None,
            "trace_id": trace_id,
        },
    )


exception_handlers = {
    RequestValidationError: validation_error_handler,
    AppError: app_error_handler,
    Exception: unhandled_error_handler,
}
