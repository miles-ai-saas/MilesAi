"""智能体对话调用记录辅助函数测试。"""

from datetime import UTC, datetime, timedelta

from miles_common.exceptions import BadRequestError
from miles_portal.tenant.agents.services.call_records import (
    build_steps_summary,
    correlation_window,
    count_tool_calls,
    is_compliance_block,
    preview_text,
)


def test_preview_text_truncates():
    assert preview_text("hello") == "hello"
    assert preview_text("x" * 250).endswith("…")
    assert len(preview_text("x" * 250)) == 201


def test_build_steps_summary():
    steps = [{"type": "planner", "label": "规划"}, {"type": "subagent", "name": "检索员"}]
    summary = build_steps_summary(steps)
    assert summary == [
        {"type": "planner", "label": "规划"},
        {"type": "subagent", "label": "检索员"},
    ]


def test_count_tool_calls():
    steps = [{"type": "planner"}, {"type": "tool_call"}, {"type": "generate_image"}]
    assert count_tool_calls(steps) == 2


def test_is_compliance_block():
    assert is_compliance_block(BadRequestError("输入内容包含敏感词，已拦截：测试"))
    assert not is_compliance_block(BadRequestError("智能体已禁用"))


def test_correlation_window():
    created = datetime(2026, 5, 29, 12, 0, 0, tzinfo=UTC)
    start, end = correlation_window(created, latency_ms=1200)
    assert start == created - timedelta(seconds=5)
    assert end == created + timedelta(milliseconds=1200) + timedelta(seconds=30)
