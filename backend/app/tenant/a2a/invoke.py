"""自定义智能体调用外部 A2A：规则触发 + 自动规划（rules_then_plan）。"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.tenant.a2a.client import invoke_a2a_peer
from app.tenant.a2a.models import A2aPeerBinding, AgentA2aPeerRef
from app.tenant.a2a.services.host_bindings import list_host_peer_bindings
from app.tenant.a2a.services.peer_refs import list_agent_a2a_peer_refs
from app.models.agent import AgentType
from app.tenant.agents.schemas.agent import ChatRequest, ChatResponse
from app.ai_stack.langchain.chat_models import ainvoke_chat
from app.models.agent import Agent

if TYPE_CHECKING:
    from app.tenant.agents.services.agent import AgentService


def _policy(agent: Agent) -> str:
    return str((agent.config or {}).get("a2a_invoke_policy", "rules_then_plan"))


def _max_calls(agent: Agent) -> int:
    return int((agent.config or {}).get("max_a2a_calls_per_turn", 2))


def _query_matches_keywords(query: str, keywords: list[str]) -> bool:
    q = query.lower()
    for kw in keywords:
        if kw and kw.lower() in q:
            return True
    return False


def _peer_keywords(ref: AgentA2aPeerRef | A2aPeerBinding) -> list[str]:
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


def _peer_catalog(refs: list[AgentA2aPeerRef] | list[A2aPeerBinding]) -> str:
    lines = []
    for ref in refs:
        peer = ref.peer
        if not peer:
            continue
        kws = _peer_keywords(ref)
        kw_txt = f" 规则关键词={','.join(kws)}" if kws else ""
        hint = f"（{ref.role_hint}）" if ref.role_hint else ""
        lines.append(
            f"- peer_id={peer.id} 名称={peer.name}{hint}{kw_txt} "
            f"Card名={peer.card_display_name or '-'}"
        )
    return "\n".join(lines)


def _parse_a2a_plan(raw: str) -> list[dict]:
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
    """规划层：由主模型选择要调用的外部 peer（未命中规则时）。"""
    if not parent.model_config:
        return []
    exclude = exclude_peer_ids or set()
    candidates = [r for r in refs if r.peer and str(r.peer.id) not in exclude]
    if not candidates:
        return []

    catalog = _peer_catalog(candidates)
    prompt = (
        "你是任务规划器。用户问题可能需要调用外部 A2A 智能体（已登记 Agent Card）。\n"
        "若不需要外部协助，输出 {\"a2a_steps\":[]}。\n"
        "若需要，输出 {\"a2a_steps\":[{\"peer_id\":\"uuid\",\"task\":\"发给外部 Agent 的子任务\"}]}\n"
        f"可选外部 Agent：\n{catalog}\n\n用户问题：{query}"
    )
    raw = await ainvoke_chat(
        parent.model_config,
        [{"role": "user", "content": prompt}],
        temperature=0.2,
        db=db,
        tenant_id=tenant_id,
    )
    plan = _parse_a2a_plan(raw)
    allowed = {str(r.peer.id) for r in candidates if r.peer}
    return [p for p in plan if p.get("peer_id") in allowed]


async def execute_a2a_calls(
    refs: list[AgentA2aPeerRef] | list[A2aPeerBinding],
    plan_items: list[dict],
    *,
    steps: list[dict],
) -> list[str]:
    blocks: list[str] = []
    ref_by_peer = {str(r.peer_id): r for r in refs if r.peer}

    for item in plan_items:
        pid = str(item.get("peer_id", ""))
        ref = ref_by_peer.get(pid)
        if not ref or not ref.peer:
            steps.append({"type": "a2a_skip", "reason": "非法 peer_id", "peer_id": pid})
            continue
        task = str(item.get("task", ""))
        try:
            answer = await invoke_a2a_peer(ref.peer, task)
            name = ref.peer.card_display_name or ref.peer.name
            steps.append(
                {
                    "type": "a2a_peer",
                    "peer_id": pid,
                    "peer_name": name,
                    "role_hint": ref.role_hint,
                    "trigger": item.get("trigger", "plan"),
                    "task": task[:300],
                    "output_preview": answer[:500],
                }
            )
            blocks.append(f"【外部 A2A · {name}】\n{answer}")
        except Exception as exc:
            steps.append(
                {
                    "type": "a2a_error",
                    "peer_id": pid,
                    "peer_name": ref.peer.name,
                    "error": str(exc)[:300],
                }
            )
    return blocks


def build_rule_plan_items(
    rule_refs: list[AgentA2aPeerRef] | list[A2aPeerBinding],
    query: str,
) -> list[dict]:
    return [
        {
            "peer_id": str(r.peer_id),
            "task": query,
            "trigger": "rule",
        }
        for r in rule_refs
        if r.peer
    ]


async def resolve_a2a_plan_items(
    agent: Agent,
    refs: list[AgentA2aPeerRef] | list[A2aPeerBinding],
    query: str,
    *,
    db: Any = None,
    tenant_id: Any = None,
) -> tuple[list[dict], list[dict]]:
    """返回 (plan_items, preliminary_steps)。"""
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

    if policy == "rules_only":
        return plan_items[:max_calls], pre_steps

    if policy in ("rules_then_plan", "plan_only") and (
        policy == "plan_only" or len(plan_items) < max_calls
    ):
        planned = await plan_a2a_peers(
            agent,
            refs,
            query,
            exclude_peer_ids=rule_ids if policy == "rules_then_plan" else None,
            db=db,
            tenant_id=tenant_id,
        )
        if planned:
            pre_steps.append({"type": "a2a_plan", "steps": planned})
        for p in planned:
            if len(plan_items) >= max_calls:
                break
            if not any(x.get("peer_id") == p.get("peer_id") for x in plan_items):
                plan_items.append({**p, "trigger": "plan"})

    return plan_items[:max_calls], pre_steps


async def augment_response_with_a2a(
    svc: AgentService,
    agent: Agent,
    body: ChatRequest,
    base: ChatResponse,
) -> ChatResponse:
    """在已有回答上按规则/规划追加外部 A2A 调用并综合。"""
    refs = await list_agent_a2a_peer_refs(svc.db, agent.id)
    if not refs:
        return base

    steps = list(base.steps)
    plan_items, pre = await resolve_a2a_plan_items(
        agent, refs, body.query, db=svc.db, tenant_id=svc.ctx.tenant_id
    )
    steps.extend(pre)

    if not plan_items:
        return base

    blocks = await execute_a2a_calls(refs, plan_items, steps=steps)
    if not blocks:
        return ChatResponse(answer=base.answer, sources=base.sources, steps=steps)

    if agent.model_config:
        synth = (
            f"{await svc._resolve_system_prompt(agent)}\n\n"
            f"用户问题：{body.query}\n\n"
            f"本智能体初步回答：\n{base.answer}\n\n"
            "外部 A2A 智能体补充：\n"
            + "\n\n---\n\n".join(blocks)
            + "\n\n请综合以上内容，给用户完整、简洁的最终回答。"
        )
        final = await ainvoke_chat(
            agent.model_config,
            [{"role": "user", "content": synth}],
            temperature=float((agent.config or {}).get("temperature", 0.7)),
            db=svc.db,
            tenant_id=svc.ctx.tenant_id,
        )
    else:
        final = base.answer + "\n\n---\n\n" + "\n\n".join(blocks)

    return ChatResponse(answer=final, sources=base.sources, steps=steps)


async def run_a2a_augmented_chat(
    svc: AgentService,
    agent: Agent,
    body: ChatRequest,
    *,
    kb_ids: list[str],
    top_k: int,
    agent_id: UUID,
    hooks,
) -> ChatResponse:
    """无内部子智能体时：先走 RAG/直连，再 rules_then_plan 调外部 A2A。"""
    base = await svc._rag_chat(agent, body, kb_ids, top_k, agent_id, hooks)
    return await augment_response_with_a2a(svc, agent, body, base)


async def run_a2a_host_chat(
    svc: AgentService,
    agent: Agent,
    body: ChatRequest,
) -> ChatResponse:
    """A2A 宿主：仅编排外部 Peer，不走本地 KB/流程。"""
    bindings = await list_host_peer_bindings(svc.db, agent.id, enabled_only=True)
    if not bindings:
        return ChatResponse(
            answer="A2A 宿主未绑定可用的外部 Agent，请先在配置中绑定并已同步 Agent Card。",
            steps=[{"type": "a2a_host", "error": "no_peers"}],
        )
    if not agent.model_config_id:
        return ChatResponse(
            answer="A2A 宿主须配置编排模型。",
            steps=[{"type": "a2a_host", "error": "no_model"}],
        )

    steps: list[dict] = [{"type": "a2a_host", "engine": "rules_then_plan"}]
    plan_items, pre = await resolve_a2a_plan_items(
        agent, bindings, body.query, db=svc.db, tenant_id=svc.ctx.tenant_id
    )
    steps.extend(pre)

    if not plan_items:
        prompt = (
            f"{await svc._resolve_system_prompt(agent)}\n\n"
            f"用户问题：{body.query}\n\n"
            "当前未命中外部调用规则，且规划器未选择外部 Agent。"
            "请根据你的编排提示，直接回答或说明需要用户补充信息。"
        )
        answer = await ainvoke_chat(
            agent.model_config,
            [{"role": "user", "content": prompt}],
            temperature=float((agent.config or {}).get("temperature", 0.7)),
            db=svc.db,
            tenant_id=svc.ctx.tenant_id,
        )
        return ChatResponse(answer=answer, steps=steps)

    blocks = await execute_a2a_calls(bindings, plan_items, steps=steps)
    if not blocks:
        return ChatResponse(
            answer="外部 A2A 调用未返回有效结果，请检查 Peer 连通性。",
            steps=steps,
        )

    synth = (
        f"{await svc._resolve_system_prompt(agent)}\n\n"
        f"用户问题：{body.query}\n\n"
        "各外部 A2A 智能体结果：\n"
        + "\n\n---\n\n".join(blocks)
        + "\n\n请综合以上外部结果，给用户完整、简洁的最终回答。"
    )
    final = await ainvoke_chat(
        agent.model_config,
        [{"role": "user", "content": synth}],
        temperature=float((agent.config or {}).get("temperature", 0.7)),
        db=svc.db,
        tenant_id=svc.ctx.tenant_id,
    )
    return ChatResponse(answer=final, sources=[], steps=steps)
