"""流程控制节点。"""

import pytest

from miles_ai.flow_runtime.nodes.control_nodes import condition_branch, parallel_join
from miles_ai.flow_runtime.types import RunContext


@pytest.mark.asyncio
async def test_condition_has_hits():
    ctx = RunContext(tenant_id="00000000-0000-0000-0000-000000000001")
    out = await condition_branch({"mode": "has_hits"}, {"hits": [{"score": 0.9}]}, ctx)
    assert out["branch"] == "true"


@pytest.mark.asyncio
async def test_condition_score_above():
    ctx = RunContext(tenant_id="00000000-0000-0000-0000-000000000001")
    out = await condition_branch(
        {"mode": "score_above", "threshold": 0.5},
        {"hits": [{"score": 0.3}]},
        ctx,
    )
    assert out["branch"] == "false"


@pytest.mark.asyncio
async def test_parallel_join_concat():
    ctx = RunContext(tenant_id="00000000-0000-0000-0000-000000000001")
    out = await parallel_join(
        {"merge_strategy": "concat_text"},
        {"a": "hello", "b": "world"},
        ctx,
    )
    assert "hello" in str(out["output"])
    assert "world" in str(out["output"])
