"""API 与分页通用 Pydantic 模型。"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一信封：code/message/data；异常响应可能带 trace_id。"""

    code: int = 0
    message: str = "ok"
    data: T | None = None
    trace_id: str | None = None


class PageParams(BaseModel):
    page: int = Field(1, ge=1)
    size: int = Field(50, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
