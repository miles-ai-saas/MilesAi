"""请求级 trace_id：中间件写入，响应构造与日志可读取。"""

from contextvars import ContextVar, Token

_trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)


def set_trace_id(trace_id: str) -> Token[str | None]:
    """写入当前上下文的 trace_id，返回可用于 reset 的 Token。"""
    return _trace_id_var.set(trace_id)


def reset_trace_id(token: Token[str | None]) -> None:
    """恢复 ``set_trace_id`` 之前的取值（请求结束调用）。"""
    _trace_id_var.reset(token)


def get_trace_id() -> str | None:
    """读取当前请求的 trace_id，未设置时返回 None。"""
    return _trace_id_var.get()
