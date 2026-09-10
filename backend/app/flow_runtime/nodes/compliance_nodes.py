"""ComplianceCheck 画布节点：对上游文本进行敏感词扫描。

词表经 ``RunContext.load_scan_words``（L1 注入）加载；扫描算法取中立域
``CompliancePipeline``（``app.models.compliance.pipeline``，子串匹配）。
返回 {passed, hits, hit_count, blocked, mode}。
mode=warn 仅标记，mode=block 时 has_block=True 可接入 ConditionBranch 做路由分流。
"""

from __future__ import annotations

from typing import Any

from app.common.exceptions import BadRequestError
from app.flow_runtime.types import RunContext
from app.models.compliance.pipeline import CompliancePipeline


async def compliance_check(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> dict[str, Any]:
    """对文本进行敏感词扫描。

    node_data:
        mode: warn（仅标记）/ block（拦截并返回告警）
        input_key: 从 inputs 中取哪个 key（默认 "input"）
    """
    text = ""
    input_key = node_data.get("input_key") or "input"

    if input_key in inputs:
        val = inputs[input_key]
        text = str(val) if val else ""
    elif "input" in inputs:
        text = str(inputs.get("input", ""))

    if not text:
        return {"passed": True, "reason": "无输入文本", "text": ""}

    mode = node_data.get("mode") or "warn"

    if ctx.load_scan_words is None:
        raise BadRequestError("运行上下文未提供敏感词加载回调")
    words = await ctx.load_scan_words(ctx.tenant_id)

    if not words:
        return {"passed": True, "reason": "未配置敏感词库", "text": text[:200]}

    pipeline = CompliancePipeline(words)
    result = pipeline.scan(text)

    hits = [{"word": m.word, "action": m.action.value} for m in result.matches]
    passed = len(hits) == 0

    return {
        "passed": passed,
        "hits": hits,
        "hit_count": len(hits),
        "mode": mode,
        "blocked": result.has_block if mode == "block" else False,
        "text": text[:500],
    }
