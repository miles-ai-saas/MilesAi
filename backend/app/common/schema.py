"""API 与分页通用 Pydantic 模型。"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一信封：code/message/data；异常响应可能带 trace_id。"""

    code: int = Field(default=0, description="业务状态码，0 表示成功")
    message: str = Field(default="ok", description="提示信息")
    data: T | None = Field(default=None, description="响应载荷")
    trace_id: str | None = Field(default=None, description="请求追踪 ID（错误时便于排查）")


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1, description="页码，从 1 开始")
    size: int = Field(default=50, ge=1, le=100, description="每页条数")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


class PageResult(BaseModel, Generic[T]):
    items: list[T] = Field(description="当前页数据")
    total: int = Field(description="总记录数")
    page: int = Field(description="当前页码")
    size: int = Field(description="每页条数")
