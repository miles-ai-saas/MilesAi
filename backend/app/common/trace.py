"""请求级 trace_id：中间件写入，响应构造与日志可读取。"""

from contextvars import ContextVar, Token

_trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)


def set_trace_id(trace_id: str) -> Token[str | None]:
    return _trace_id_var.set(trace_id)


def reset_trace_id(token: Token[str | None]) -> None:
    _trace_id_var.reset(token)


def get_trace_id() -> str | None:
    return _trace_id_var.get()
