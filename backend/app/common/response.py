"""统一 API 响应构造。

成功：code=0；删除成功常为 ok(message=\"已删除\", data=None)，前端勿将 data=null 判为失败。
"""

from typing import TypeVar

from app.common.schema import ApiResponse, PageResult
from app.common.trace import get_trace_id

T = TypeVar("T")


def ok(data: T | None = None, message: str = "ok", code: int = 0) -> ApiResponse[T]:
    """构造成功响应；data 可为 None（如无 body 的删除）。"""
    return ApiResponse(code=code, message=message, data=data, trace_id=get_trace_id())


def fail(message: str, code: int = 1, data: T | None = None) -> ApiResponse[T]:
    """业务层显式失败（多数错误由 AppError 处理器返回）。"""
    return ApiResponse(code=code, message=message, data=data, trace_id=get_trace_id())


def page_ok(
    items: list[T],
    total: int,
    page: int,
    size: int,
    message: str = "ok",
) -> ApiResponse[PageResult[T]]:
    """分页列表包装为 ApiResponse[PageResult]。"""
    return ok(
        data=PageResult(items=items, total=total, page=page, size=size),
        message=message,
    )
