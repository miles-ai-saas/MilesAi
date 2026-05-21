"""统一 API 响应构造。"""

from typing import TypeVar

from app.common.schema import ApiResponse, PageResult

T = TypeVar("T")


def ok(data: T | None = None, message: str = "ok", code: int = 0) -> ApiResponse[T]:
    return ApiResponse(code=code, message=message, data=data)


def fail(message: str, code: int = 1, data: T | None = None) -> ApiResponse[T]:
    return ApiResponse(code=code, message=message, data=data)


def page_ok(
    items: list[T],
    total: int,
    page: int,
    size: int,
    message: str = "ok",
) -> ApiResponse[PageResult[T]]:
    return ok(
        data=PageResult(items=items, total=total, page=page, size=size),
        message=message,
    )
