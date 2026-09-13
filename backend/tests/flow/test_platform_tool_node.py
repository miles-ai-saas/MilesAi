"""画布 PlatformTool 节点。

Task 1 起节点不再直接开 DB 会话调 L1 工具执行：``platform_tool`` 仅做
slug/params 合并调度，执行经 ``RunContext.invoke_platform_tool`` 回调
（L1 注入；None 时节点报「未装配」）。
"""

from uuid import uuid4

import pytest

from miles_ai.flow_runtime.nodes.tool_nodes import _build_invoke_params, platform_tool
from miles_ai.flow_runtime.types import RunContext
from miles_common.exceptions import BadRequestError


def _ctx(**overrides) -> RunContext:
    base = dict(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),
        agent_id=str(uuid4()),
        kb_ids=["kb-1"],
    )
    base.update(overrides)
    return RunContext(**base)


def test_build_invoke_params_kb_default():
    ctx = RunContext(tenant_id=str(uuid4()), kb_ids=["kb-1", "kb-2"])
    params = _build_invoke_params(
        {"tool_slug": "knowledge_search", "merge_input": True},
        {"query": "hello"},
        ctx,
    )
    assert params["query"] == "hello"
    assert params["kb_id"] == "kb-1"


@pytest.mark.parametrize(
    ("node_data", "inputs", "expected"),
    [
        # param_from_input 命中则注入指定参数；merge_input=False 不再合并上游
        (
            {
                "tool_slug": "calculator",
                "params": {"x": 1},
                "param_from_input": {"y": "from_in"},
                "merge_input": False,
            },
            {"from_in": 2, "other": 3},
            {"x": 1, "y": 2},
        ),
        # merge_input=True 合并上游未命名变量（input/true/false 除外）
        (
            {"tool_slug": "calculator", "params": {"x": 1}, "merge_input": True},
            {"other": 3, "input": "忽略"},
            {"x": 1, "other": 3},
        ),
    ],
)
def test_build_invoke_params_param_from_input_and_merge(node_data, inputs, expected):
    params = _build_invoke_params(node_data, inputs, _ctx())
    assert params == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("confirmed_kw", "expected"),
    [
        ({"confirmed": True}, True),
        ({}, True),  # 缺省视为 True
        ({"confirmed": False}, False),
    ],
)
async def test_platform_tool_dispatches_via_callback(confirmed_kw, expected):
    captured: dict = {}

    async def _invoker(slug, params, ctx, *, confirmed):
        captured["slug"] = slug
        captured["params"] = params
        captured["ctx"] = ctx
        captured["confirmed"] = confirmed
        return {"ok": 1}

    ctx = _ctx(invoke_platform_tool=_invoker)
    node_data = {"tool_slug": "calculator", "params": {"expr": "1+1"}, **confirmed_kw}
    out = await platform_tool(node_data, {"input": "忽略"}, ctx)

    assert out == {"output": {"ok": 1}, "tool_slug": "calculator"}
    assert captured["slug"] == "calculator"
    assert captured["params"] == {"expr": "1+1"}
    assert captured["ctx"] is ctx
    assert captured["confirmed"] is expected


@pytest.mark.asyncio
async def test_platform_tool_unassembled_raises():
    ctx = _ctx()  # invoke_platform_tool 缺省为 None
    assert ctx.invoke_platform_tool is None
    with pytest.raises(BadRequestError, match="未装配"):
        await platform_tool({"tool_slug": "calculator"}, {}, ctx)
