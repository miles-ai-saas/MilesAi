"""全局异常处理器。

AppError → JSON {code, message, data:null, trace_id}；校验失败 422；未捕获 500（非 debug 时隐藏细节）。
"""

from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.logging import get_logger
from app.common.exceptions import AppError

logger = get_logger(__name__)


def _format_validation_message(exc: RequestValidationError) -> str:
    if not exc.errors():
        return "参数校验失败"
    err = exc.errors()[0]
    msg = str(err.get("msg") or "参数校验失败")
    for prefix in ("Value error, ", "Assertion failed, "):
        if msg.startswith(prefix):
            msg = msg[len(prefix) :]
    loc = err.get("loc") or ()
    parts = [str(x) for x in loc if x not in ("body", "query", "path")]
    if parts:
        return f"{'.'.join(parts)}: {msg}"
    return msg


def _cors_headers(request: Request) -> dict[str, str]:
    origin = request.headers.get("origin")
    if origin and origin in get_settings().cors_origin_list:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }
    return {}


def _error_envelope(
    request: Request,
    *,
    status_code: int,
    code: int,
    message: str,
) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse(
        status_code=status_code,
        headers=_cors_headers(request),
        content={
            "code": code,
            "message": message,
            "data": None,
            "trace_id": trace_id,
        },
    )


def _public_message(exc: Exception) -> str:
    """对外错误文案：开发环境可带细节，生产环境泛化。"""
    settings = get_settings()
    if settings.debug:
        return str(exc)
    if isinstance(exc, SQLAlchemyError):
        orig = getattr(exc, "orig", None)
        detail = str(orig or exc).lower()
        if "does not exist" in detail or "undefinedcolumn" in detail:
            return "数据库结构未同步，请执行 python cli.py migrate 后重试"
        return "数据库操作失败，请稍后重试或联系管理员"
    return "服务器内部错误"


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    detail = _format_validation_message(exc)
    return _error_envelope(request, status_code=422, code=422, message=detail)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return _error_envelope(
        request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
    )


async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception(
        "SQLAlchemy error path=%s trace_id=%s",
        request.url.path,
        getattr(request.state, "trace_id", None),
    )
    return _error_envelope(
        request,
        status_code=500,
        code=500,
        message=_public_message(exc),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "Unhandled error path=%s trace_id=%s",
        request.url.path,
        getattr(request.state, "trace_id", None),
    )
    return _error_envelope(
        request,
        status_code=500,
        code=500,
        message=_public_message(exc),
    )


exception_handlers = {
    RequestValidationError: validation_error_handler,
    AppError: app_error_handler,
    SQLAlchemyError: sqlalchemy_error_handler,
    Exception: unhandled_error_handler,
}
