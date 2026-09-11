"""画布 ComplianceCheck 节点：词表经 RunContext 回调注入，算法取中立域 pipeline。"""

from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError
from miles_ai.flow_runtime.nodes import compliance_nodes
from miles_ai.flow_runtime.types import RunContext
from miles_core.models.compliance.constants import SensitiveAction


@pytest.mark.asyncio
async def test_compliance_check_warn_hit():
    async def _words(_tenant_id: str):
        return [("敏感词", SensitiveAction.WARN)]

    ctx = RunContext(tenant_id=str(uuid4()), load_scan_words=_words)
    out = await compliance_nodes.compliance_check(
        {"mode": "warn"},
        {"input": "含敏感词文本"},
        ctx,
    )
    assert out["passed"] is False
    assert out["hit_count"] == 1
    assert out["blocked"] is False
    assert out["hits"][0]["word"] == "敏感词"
    assert out["hits"][0]["action"] == "warn"
    assert out["mode"] == "warn"
    assert "text" in out


@pytest.mark.asyncio
async def test_compliance_check_block_hit():
    async def _words(_tenant_id: str):
        return [("禁词", SensitiveAction.BLOCK)]

    ctx = RunContext(tenant_id=str(uuid4()), load_scan_words=_words)
    out = await compliance_nodes.compliance_check(
        {"mode": "block"},
        {"input": "这里出现禁词"},
        ctx,
    )
    assert out["blocked"] is True
    assert out["passed"] is False


@pytest.mark.asyncio
async def test_compliance_check_empty_words():
    async def _words(_tenant_id: str):
        return []

    ctx = RunContext(tenant_id=str(uuid4()), load_scan_words=_words)
    out = await compliance_nodes.compliance_check(
        {"mode": "warn"},
        {"input": "含敏感词文本"},
        ctx,
    )
    assert out["passed"] is True
    assert out["reason"] == "未配置敏感词库"
    assert out["text"] == "含敏感词文本"[:200]


@pytest.mark.asyncio
async def test_compliance_check_empty_input_skips_callback():
    calls = 0

    async def _words(_tenant_id: str):
        nonlocal calls
        calls += 1
        return [("敏感词", SensitiveAction.WARN)]

    ctx = RunContext(tenant_id=str(uuid4()), load_scan_words=_words)
    out = await compliance_nodes.compliance_check({"mode": "warn"}, {}, ctx)
    assert out["passed"] is True
    assert out["reason"] == "无输入文本"
    assert out["text"] == ""
    assert calls == 0


@pytest.mark.asyncio
async def test_compliance_check_without_callback_raises():
    ctx = RunContext(tenant_id=str(uuid4()))
    with pytest.raises(BadRequestError, match="敏感词加载回调"):
        await compliance_nodes.compliance_check(
            {"mode": "warn"},
            {"input": "含敏感词文本"},
            ctx,
        )


@pytest.mark.asyncio
async def test_compliance_check_custom_input_key():
    async def _words(_tenant_id: str):
        return [("敏感词", SensitiveAction.WARN)]

    ctx = RunContext(tenant_id=str(uuid4()), load_scan_words=_words)
    out = await compliance_nodes.compliance_check(
        {"input_key": "foo"},
        {"foo": "命中敏感词"},
        ctx,
    )
    assert out["hit_count"] == 1
