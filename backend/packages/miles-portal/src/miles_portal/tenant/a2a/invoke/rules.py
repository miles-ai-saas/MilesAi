"""A2A 规则层：策略读取与关键词命中。"""

from __future__ import annotations

from miles_core.models.agent import Agent
from miles_portal.tenant.a2a.models import (
    A2aInvokePolicy,
    A2aPeerBinding,
    A2aPlanTrigger,
    AgentA2aPeerRef,
)


def _policy(agent: Agent) -> A2aInvokePolicy:
    """读取 A2A 调用策略配置。"""
    raw = str((agent.config or {}).get("a2a_invoke_policy", A2aInvokePolicy.RULES_THEN_PLAN.value))
    try:
        return A2aInvokePolicy(raw)
    except ValueError:
        return A2aInvokePolicy.RULES_THEN_PLAN


def _max_calls(agent: Agent) -> int:
    """单轮最多调用的外部 peer 数。"""
    return int((agent.config or {}).get("max_a2a_calls_per_turn", 2))


def _query_matches_keywords(query: str, keywords: list[str]) -> bool:
    """用户问题是否命中任一 trigger_keywords。"""
    q = query.lower()
    for kw in keywords:
        if kw and kw.lower() in q:
            return True
    return False


def _peer_keywords(ref: AgentA2aPeerRef | A2aPeerBinding) -> list[str]:
    """从 peer 引用行读取关键词列表。"""
    kws = ref.trigger_keywords if isinstance(ref.trigger_keywords, list) else []
    return [str(k) for k in kws]


def evaluate_rule_triggered_peers(
    query: str,
    refs: list[AgentA2aPeerRef] | list[A2aPeerBinding],
) -> list[AgentA2aPeerRef] | list[A2aPeerBinding]:
    """规则层：命中 trigger_keywords 的 peer 必须调用。"""
    hits = []
    for ref in refs:
        if not ref.enabled or not ref.peer:
            continue
        kws = _peer_keywords(ref)
        if kws and _query_matches_keywords(query, kws):
            hits.append(ref)
    return hits


def build_rule_plan_items(
    rule_refs: list[AgentA2aPeerRef] | list[A2aPeerBinding],
    query: str,
) -> list[dict]:
    """规则层命中 peer → ``{peer_id, task, trigger: rule}`` 计划项（task 为整句用户 query）。"""
    return [
        {
            "peer_id": str(r.peer_id),
            "task": query,
            "trigger": A2aPlanTrigger.RULE.value,
        }
        for r in rule_refs
        if r.peer
    ]
