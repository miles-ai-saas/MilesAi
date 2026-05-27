"""ComplianceCheck 画布节点：对上游文本进行敏感词扫描。

读取租户已绑定词库，使用 CompliancePipeline（子串匹配）扫描输入文本。
返回 {passed, hits, hit_count, blocked, mode}。
mode=warn 仅标记，mode=block 时 has_block=True 可接入 ConditionBranch 做路由分流。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.flow_runtime.types import RunContext
from app.infra.db import get_sync_db
from app.tenant.compliance.services.pipeline import CompliancePipeline
from app.tenant.compliance.services.word_resolve import load_tenant_scan_words


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

    with get_sync_db() as db:
        words = load_tenant_scan_words(db, UUID(ctx.tenant_id))

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
