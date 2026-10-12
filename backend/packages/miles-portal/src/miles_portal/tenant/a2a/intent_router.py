"""
A2A 意图路由（一期）：用一次结构化 LLM 调用选择外部 Peer。

与 ``plan_a2a_peers`` 的差异：prompt 强调「意图分类 / 是否需要外部协助」，
而非通用任务拆解；配置见 ``agent.config.a2a_intent_router``。
"""

from __future__ import annotations

import time
from typing import Any

from miles_core.models.agent import Agent
from miles_integrations.langchain.chat_models import ainvoke_chat
from miles_portal.tenant.a2a.models import A2aPeerBinding, AgentA2aPeerRef
from miles_portal.tenant.models.services.model_resolve import resolve_model_for_invoke
from miles_portal.tenant.models.services.usage import ChatUsageSink


def intent_router_enabled(agent: Agent) -> bool:
    """``config.a2a_intent_router.enabled`` 为真时启用意图路由规划。"""
    cfg = (agent.config or {}).get("a2a_intent_router")
    if not isinstance(cfg, dict):
        return False
    return bool(cfg.get("enabled"))


def intent_router_config(agent: Agent) -> dict[str, Any]:
    """返回规范化后的意图路由配置块。"""
    raw = (agent.config or {}).get("a2a_intent_router")
    if not isinstance(raw, dict):
        return {"enabled": False}
    return {
        "enabled": bool(raw.get("enabled")),
        "model_config_id": str(raw["model_config_id"]) if raw.get("model_config_id") else None,
    }


async def route_a2a_peers_by_intent(
    parent: Agent,
    refs: list[AgentA2aPeerRef] | list[A2aPeerBinding],
    query: str,
    *,
    exclude_peer_ids: set[str] | None = None,
    db: Any = None,
    tenant_id: Any = None,
    peer_catalog_fn,
    parse_plan_fn,
) -> tuple[list[dict], dict[str, Any]]:
    """
    意图路由：输出 ``{"a2a_steps":[{"peer_id","task"},...]}``。

    返回 ``(plan_items, step_meta)``；``step_meta`` 供写入 ``a2a_intent_router`` step。
    ``peer_catalog_fn`` / ``parse_plan_fn`` 由 ``invoke`` 注入，避免循环导入。
    """
    started = time.perf_counter()
    meta: dict[str, Any] = {
        "engine": "intent_llm",
        "selected_peer_ids": [],
        "latency_ms": 0,
        "empty_reason": None,
    }

    if not parent.model_config:
        meta["empty_reason"] = "no_model"
        meta["latency_ms"] = int((time.perf_counter() - started) * 1000)
        return [], meta

    exclude = exclude_peer_ids or set()
    candidates = [r for r in refs if r.peer and str(r.peer.id) not in exclude]
    if not candidates:
        meta["empty_reason"] = "no_candidates"
        meta["latency_ms"] = int((time.perf_counter() - started) * 1000)
        return [], meta

    catalog = peer_catalog_fn(candidates)
    prompt = (
        "你是意图路由器。根据用户问题，判断是否需要调用已登记的外部 A2A 智能体。\n"
        "规则：\n"
        "1. 若本地即可回答，或不匹配任何外部 Agent 职责，输出 {\"a2a_steps\":[]}。\n"
        "2. 若需要外部协助，只选择最相关的 1–2 个 peer，为每个 peer 写简洁 task。\n"
        "3. peer_id 必须来自下列目录，禁止编造。\n"
        '输出 JSON：{"a2a_steps":[{"peer_id":"uuid","task":"子任务"}]}。\n'
        f"外部 Agent 目录：\n{catalog}\n\n用户问题：{query}"
    )

    model = await resolve_model_for_invoke(db, parent.model_config, tenant_id)
    usage_sink = ChatUsageSink(
        tenant_id=tenant_id,
        model=model,
        source_id=parent.id,
    )
    if db is not None:
        await db.commit()
    raw = await ainvoke_chat(
        model,
        [{"role": "user", "content": prompt}],
        temperature=0.1,
        usage_sink=usage_sink,
    )
    plan = parse_plan_fn(raw)
    allowed = {str(r.peer.id) for r in candidates if r.peer}
    filtered = [p for p in plan if p.get("peer_id") in allowed]
    meta["selected_peer_ids"] = [str(p.get("peer_id")) for p in filtered]
    if not filtered and not plan:
        meta["empty_reason"] = "empty_plan"
    elif not filtered and plan:
        meta["empty_reason"] = "invalid_peer_ids"
    meta["latency_ms"] = int((time.perf_counter() - started) * 1000)
    return filtered, meta
