"""``record_runner_session`` 上下文管理器的直接单测。

该管理器承载「每次 Runner 调用恰好写一条审计」这一不变量（4 个调用点共用），
故除各调用点的行为测试外，单独覆盖管理器自身的契约：

- 正常退出 → 恰好一条 ``success``，且写在 with 体之后；
- ``BadRequestError`` → 恰好一条 ``error``（带 message）并原样抛出；
- 其他异常 → 不写审计，原样冒泡；
- 位置实参与关键字实参原样转发给写入函数；
- 调用方误传 ``status``/``duration_ms``/``error_message`` → 进入 with 体之前即报错。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from miles_common.exceptions import BadRequestError
from miles_portal.tenant.mcp.runner import audit as audit_mod


class _Clock:
    """递增单调时钟：每对 (start, end) 差值恒为 250ms。"""

    def __init__(self, start: float = 1.0, step: float = 0.25) -> None:
        self._value = start
        self._step = step

    def __call__(self) -> float:
        current = self._value
        self._value += self._step
        return current


@pytest.fixture
def writer(monkeypatch):
    calls: list[tuple] = []

    async def _write(*args, **kwargs):  # noqa: ANN002, ANN003
        calls.append((args, kwargs))

    monkeypatch.setattr(audit_mod, "time", SimpleNamespace(monotonic=_Clock()))
    return SimpleNamespace(calls=calls, fn=_write)


# --------------------------------------------------------------------------- #
# 正常与失败路径
# --------------------------------------------------------------------------- #


async def test_success_writes_exactly_one_row_with_elapsed(writer):  # noqa: ANN001
    async with audit_mod.record_runner_session(writer.fn, "db", tenant_id="t", tool_name="x"):
        pass

    ((args, kwargs),) = writer.calls
    assert args == ("db",)
    assert kwargs["status"] == "success"
    assert kwargs["duration_ms"] == 250
    assert kwargs["tenant_id"] == "t"
    assert kwargs["tool_name"] == "x"
    assert "error_message" not in kwargs  # 成功路径不带该参数


async def test_bad_request_writes_exactly_one_error_row_and_reraises(writer):  # noqa: ANN001
    with pytest.raises(BadRequestError):
        async with audit_mod.record_runner_session(writer.fn, "db", spec="s"):
            raise BadRequestError("沙箱不可达")

    ((args, kwargs),) = writer.calls
    assert args == ("db",)
    assert kwargs["status"] == "error"
    assert kwargs["error_message"] == "沙箱不可达"
    assert kwargs["duration_ms"] == 250
    assert kwargs["spec"] == "s"


async def test_non_bad_request_exception_writes_nothing(writer):  # noqa: ANN001
    with pytest.raises(RuntimeError):
        async with audit_mod.record_runner_session(writer.fn, "db"):
            raise RuntimeError("程序缺陷")

    assert writer.calls == []


async def test_audit_is_written_after_body_exits(writer):  # noqa: ANN001
    """审计在 with 体结束时写，而非进入时；避免把未完成的工作记成成功。"""
    async with audit_mod.record_runner_session(writer.fn, "db"):
        assert writer.calls == []

    assert len(writer.calls) == 1


# --------------------------------------------------------------------------- #
# 注入参数的护栏
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("injected", ["status", "duration_ms", "error_message"])
async def test_injected_kwargs_rejected_before_body_runs(writer, injected):  # noqa: ANN001
    body_ran = False

    with pytest.raises(TypeError, match=injected):
        async with audit_mod.record_runner_session(writer.fn, "db", **{injected: "x"}):
            body_ran = True

    assert body_ran is False
    assert writer.calls == []


async def test_positional_args_are_forwarded_verbatim(writer):  # noqa: ANN001
    """位置实参（如 db）应与直接调用写入函数时一致地转发。"""
    db = object()

    async with audit_mod.record_runner_session(writer.fn, db, spec="s", tool_name="t"):
        pass

    ((args, _kwargs),) = writer.calls
    assert args == (db,)
