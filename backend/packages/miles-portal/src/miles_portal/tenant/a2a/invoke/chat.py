"""A2A 增强对话与宿主编排入口。"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from miles_core.models.agent import Agent
from miles_portal.tenant.a2a.models import A2aInvokePolicy
from miles_portal.tenant.agents.schemas.agent import ChatRequest, ChatResponse

if TYPE_CHECKING:
    from miles_portal.tenant.agents.services.agent import AgentService


async def augment_response_with_a2a(
    svc: AgentService,
    agent: Agent,
    body: ChatRequest,
    base: ChatResponse,
) -> ChatResponse:
    """
    在本地回答（含 RAG ``sources``）之上追加外部 A2A 结果。

    ``base`` 通常来自 ``_rag_chat`` 或子 Agent 规划；无 peer 时原样返回。
    有编排模型时用 LLM 综合，否则拼接文本块。
    """
    from miles_portal.tenant.a2a import invoke as invoke_mod

    refs = await invoke_mod.list_agent_a2a_peer_refs(svc.db, agent.id)
    if not refs:
        return base

    steps = list(base.steps)
    plan_items, pre = await invoke_mod.resolve_a2a_plan_items(
        agent, refs, body.query, db=svc.db, tenant_id=svc.ctx.tenant_id
    )
    steps.extend(pre)

    if not plan_items:
        return base

    blocks = await invoke_mod.execute_a2a_calls(refs, plan_items, steps=steps)
    if not blocks:
        return ChatResponse(answer=base.answer, sources=base.sources, steps=steps)

    if agent.model_config:
        synth = (
            f"{await svc.resolve_system_prompt(agent)}\n\n"
            f"用户问题：{body.query}\n\n"
            f"本智能体初步回答：\n{base.answer}\n\n"
            "外部 A2A 智能体补充：\n" + "\n\n---\n\n".join(blocks) + "\n\n请综合以上内容，给用户完整、简洁的最终回答。"
        )
        model = await svc.resolve_invoke_model(agent.model_config)
        usage_sink = svc.chat_usage_sink(model, source_id=agent.id)
        final = await invoke_mod.ainvoke_chat(
            model,
            [{"role": "user", "content": synth}],
            temperature=float((agent.config or {}).get("temperature", 0.7)),
            usage_sink=usage_sink,
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
    """
    有 A2A Peer、无子智能体时的对话路径。

    ``kb_ids`` 来自 ``agent.knowledge_bases``；本地答案由 RAG/直连产生后再调外部 Agent。
    """
    from miles_portal.tenant.a2a import invoke as invoke_mod

    base = await svc.rag_chat(agent, body, kb_ids, top_k, agent_id, hooks)
    return await invoke_mod.augment_response_with_a2a(svc, agent, body, base)


async def run_a2a_host_chat(
    svc: AgentService,
    agent: Agent,
    body: ChatRequest,
) -> ChatResponse:
    """A2A 宿主：仅编排外部 Peer，不走本地 KB/流程。"""
    from miles_portal.tenant.a2a import invoke as invoke_mod

    bindings = await invoke_mod.list_host_peer_bindings(svc.db, agent.id, enabled_only=True)
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

    steps: list[dict] = [{"type": "a2a_host", "engine": A2aInvokePolicy.RULES_THEN_PLAN.value}]
    plan_items, pre = await invoke_mod.resolve_a2a_plan_items(
        agent, bindings, body.query, db=svc.db, tenant_id=svc.ctx.tenant_id
    )
    steps.extend(pre)

    history = await invoke_mod.load_chat_history_messages(
        svc.db,
        tenant_id=svc.ctx.tenant_id,
        agent_id=agent.id,
        conversation_id=body.conversation_id,
    )
    history_block = invoke_mod.format_history_block(history)
    memory_rows, long_term = await invoke_mod.UserMemoryService(svc.db, svc.ctx).load_for_inject(
        agent=agent,
        user_id=svc.ctx.user_id,
        query=body.query,
    )
    if long_term:
        steps.append({"type": "user_memory", "items": len(memory_rows), "chars": len(long_term)})
    if history:
        steps.append({"type": "chat_memory", "history_messages": len(history), "route": "a2a_host"})

    system_prompt = await svc.resolve_system_prompt(agent)
    # 长期 → 近期，与 RAG / Flow 一致。
    system_prompt = f"{system_prompt}{long_term}{history_block}"
    model = await svc.resolve_invoke_model(agent.model_config)
    usage_sink = svc.chat_usage_sink(model, source_id=agent.id)
    temperature = float((agent.config or {}).get("temperature", 0.7))
    # 释放请求事务：Peer HTTP / 编排 LLM 期间不长时间占连接（对齐 RAG）。
    await svc.db.commit()

    if not plan_items:
        prompt = (
            f"{system_prompt}\n\n"
            f"用户问题：{body.query}\n\n"
            "当前未命中外部调用规则，且规划器未选择外部 Agent。"
            "请根据你的编排提示，直接回答或说明需要用户补充信息。"
        )
        answer = await invoke_mod.ainvoke_chat(
            model,
            [{"role": "user", "content": prompt}],
            temperature=temperature,
            usage_sink=usage_sink,
        )
        return ChatResponse(answer=answer, steps=steps)

    blocks = await invoke_mod.execute_a2a_calls(bindings, plan_items, steps=steps)
    if not blocks:
        return ChatResponse(
            answer="外部 A2A 调用未返回有效结果，请检查 Peer 连通性。",
            steps=steps,
        )

    synth = (
        f"{system_prompt}\n\n"
        f"用户问题：{body.query}\n\n"
        "各外部 A2A 智能体结果：\n" + "\n\n---\n\n".join(blocks) + "\n\n请综合以上外部结果，给用户完整、简洁的最终回答。"
    )
    final = await invoke_mod.ainvoke_chat(
        model,
        [{"role": "user", "content": synth}],
        temperature=temperature,
        usage_sink=usage_sink,
    )
    return ChatResponse(answer=final, sources=[], steps=steps)
