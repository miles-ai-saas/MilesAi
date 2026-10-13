"""A2A 规划层：目录、LLM/意图路由与计划合并。"""

from __future__ import annotations

import json
import re
from typing import Any

from miles_core.models.agent import Agent
from miles_portal.tenant.a2a.invoke.rules import (
    _max_calls,
    _peer_keywords,
    _policy,
    build_rule_plan_items,
    evaluate_rule_triggered_peers,
)
from miles_portal.tenant.a2a.models import (
    A2aInvokePolicy,
    A2aPeerBinding,
    A2aPlanTrigger,
    AgentA2aPeerRef,
)


def _peer_catalog(refs: list[AgentA2aPeerRef] | list[A2aPeerBinding]) -> str:
    """外部 Agent 目录文本，供规划 LLM 选择。"""
    lines = []
    for ref in refs:
        peer = ref.peer
        if not peer:
            continue
        kws = _peer_keywords(ref)
        kw_txt = f" 规则关键词={','.join(kws)}" if kws else ""
        hint = f"（{ref.role_hint}）" if ref.role_hint else ""
        lines.append(f"- peer_id={peer.id} 名称={peer.name}{hint}{kw_txt} Card名={peer.card_display_name or '-'}")
    return "\n".join(lines)


def _parse_a2a_plan(raw: str) -> list[dict]:
    """解析 a2a_steps JSON 规划。"""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    steps = data.get("a2a_steps") or data.get("steps")
    if not isinstance(steps, list):
        return []
    out = []
    for s in steps[:5]:
        if not isinstance(s, dict):
            continue
        pid = s.get("peer_id")
        task = s.get("task") or s.get("query")
        if pid and task:
            out.append({"peer_id": str(pid), "task": str(task)})
    return out


async def plan_a2a_peers(
    parent: Agent,
    refs: list[AgentA2aPeerRef] | list[A2aPeerBinding],
    query: str,
    *,
    exclude_peer_ids: set[str] | None = None,
    db: Any = None,
    tenant_id: Any = None,
) -> list[dict]:
    """
    规划层：编排模型输出 ``{"a2a_steps":[{"peer_id","task"},...]}``。

    ``rules_then_plan`` 时已规则命中的 peer 会从候选排除，避免重复调用。
    """
    from miles_portal.tenant.a2a import invoke as invoke_mod

    if not parent.model_config:
        return []
    exclude = exclude_peer_ids or set()
    candidates = [r for r in refs if r.peer and str(r.peer.id) not in exclude]
    if not candidates:
        return []

    catalog = _peer_catalog(candidates)
    prompt = (
        "你是任务规划器。用户问题可能需要调用外部 A2A 智能体（已登记 Agent Card）。\n"
        '若不需要外部协助，输出 {"a2a_steps":[]}。\n'
        '若需要，输出 {"a2a_steps":[{"peer_id":"uuid","task":"发给外部 Agent 的子任务"}]}\n'
        f"可选外部 Agent：\n{catalog}\n\n用户问题：{query}"
    )
    model = await invoke_mod.resolve_model_for_invoke(db, parent.model_config, tenant_id)
    usage_sink = invoke_mod.ChatUsageSink(
        tenant_id=tenant_id,
        model=model,
        source_id=parent.id,
    )
    if db is not None:
        await db.commit()
    raw = await invoke_mod.ainvoke_chat(
        model,
        [{"role": "user", "content": prompt}],
        temperature=0.2,
        usage_sink=usage_sink,
    )
    plan = _parse_a2a_plan(raw)
    allowed = {str(r.peer.id) for r in candidates if r.peer}
    return [p for p in plan if p.get("peer_id") in allowed]


async def resolve_a2a_plan_items(
    agent: Agent,
    refs: list[AgentA2aPeerRef] | list[A2aPeerBinding],
    query: str,
    *,
    db: Any = None,
    tenant_id: Any = None,
) -> tuple[list[dict], list[dict]]:
    """
    合并规则层与规划层，得到本轮外部调用计划。

    返回 ``(plan_items, preliminary_steps)``，受 ``max_a2a_calls_per_turn`` 截断。
    """
    from miles_portal.tenant.a2a import invoke as invoke_mod

    pre_steps: list[dict] = []
    policy = _policy(agent)
    max_calls = _max_calls(agent)

    rule_refs = evaluate_rule_triggered_peers(query, refs)
    if rule_refs:
        pre_steps.append(
            {
                "type": "a2a_rules",
                "matched": [str(r.peer_id) for r in rule_refs],
            }
        )

    plan_items: list[dict] = build_rule_plan_items(rule_refs, query)
    rule_ids = {str(r.peer_id) for r in rule_refs}

    if policy == A2aInvokePolicy.RULES_ONLY:
        return plan_items[:max_calls], pre_steps

    if policy in (A2aInvokePolicy.RULES_THEN_PLAN, A2aInvokePolicy.PLAN_ONLY) and (
        policy == A2aInvokePolicy.PLAN_ONLY or len(plan_items) < max_calls
    ):
        exclude = rule_ids if policy == A2aInvokePolicy.RULES_THEN_PLAN else None
        use_intent = invoke_mod.intent_router_enabled(agent)
        if use_intent:
            planned, intent_meta = await invoke_mod.route_a2a_peers_by_intent(
                agent,
                refs,
                query,
                exclude_peer_ids=exclude,
                db=db,
                tenant_id=tenant_id,
                peer_catalog_fn=_peer_catalog,
                parse_plan_fn=_parse_a2a_plan,
            )
            pre_steps.append({"type": "a2a_intent_router", **intent_meta, "steps": planned})
            trigger = A2aPlanTrigger.INTENT.value
        else:
            planned = await invoke_mod.plan_a2a_peers(
                agent,
                refs,
                query,
                exclude_peer_ids=exclude,
                db=db,
                tenant_id=tenant_id,
            )
            if planned:
                pre_steps.append({"type": "a2a_plan", "steps": planned})
            trigger = A2aPlanTrigger.PLAN.value
        for p in planned:
            if len(plan_items) >= max_calls:
                break
            if not any(x.get("peer_id") == p.get("peer_id") for x in plan_items):
                plan_items.append({**p, "trigger": trigger})

    return plan_items[:max_calls], pre_steps
