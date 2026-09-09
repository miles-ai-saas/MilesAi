"""
主智能体 + 多子智能体编排（L3）。

决策（``AgentService.chat`` 有 ``sub_agent_bindings`` 时）
-------------------------------------------------
1. ``_should_use_deepagents``：``config.planner=deepagents`` 且已安装 ``deepagents`` 包
   → ``run_deepagents_chat``（task 工具委派，共用 ``get_checkpointer()``）
2. 失败或未安装 → ``_run_platform_planned``：主模型输出 JSON ``steps``，依次 ``chat_as_child``

与 A2A / 发布流程
-----------------
子智能体路径优先于 ``published_flow`` 与单 Agent ``_rag_chat``；A2A 增强在子 Agent 返回之后另分支处理。

``config`` 常用键：``subagent_parallel``、``max_subagent_calls``、``force_platform_planner``。
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import TYPE_CHECKING
from uuid import UUID

from app.tenant.agents.schemas.agent import ChatRequest, ChatResponse
from app.integrations.deepagents.runner import deepagents_importable, run_deepagents_chat
from app.integrations.langchain.chat_models import ainvoke_chat
from app.models.agent import Agent, AgentSubAgentBinding
from app.models.agent.constants import AgentPlanner

if TYPE_CHECKING:
    from app.tenant.agents.services.agent import AgentService


def _catalog_text(bindings: list[AgentSubAgentBinding]) -> str:
    """子智能体列表文本，供规划 prompt 使用。"""
    lines = []
    for b in bindings:
        child = b.child_agent
        if not child:
            continue
        hint = f"（{b.role_hint}）" if b.role_hint else ""
        desc = (child.description or "")[:120]
        lines.append(f"- id={child.id} 名称={child.name}{hint} 描述={desc}")
    return "\n".join(lines)


def _parse_plan(raw: str) -> list[dict]:
    """解析 LLM 输出的 JSON 规划 steps。"""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    steps = data.get("steps") if isinstance(data, dict) else data
    if not isinstance(steps, list):
        return []
    out = []
    for s in steps[:10]:
        if not isinstance(s, dict):
            continue
        sid = s.get("sub_agent_id")
        task = s.get("task") or s.get("query")
        if sid and task:
            out.append({"sub_agent_id": str(sid), "task": str(task)})
    return out


async def _platform_plan(
    parent: Agent,
    bindings: list[AgentSubAgentBinding],
    query: str,
    *,
    svc: AgentService,
) -> list[dict]:
    """平台 JSON 规划器：主模型输出 sub_agent_id + task 列表。"""
    if not parent.model_config:
        return [
            {
                "sub_agent_id": str(bindings[0].child_agent_id),
                "task": query,
            }
        ]
    catalog = _catalog_text(bindings)
    prompt = (
        "你是任务规划器。根据用户问题，从下列子智能体中选择要调用的一个或多个，并给出每个子任务说明。\n"
        '仅输出 JSON：{"steps":[{"sub_agent_id":"uuid","task":"子任务描述"}]}\n\n'
        f"子智能体列表：\n{catalog}\n\n用户问题：{query}"
    )
    model = await svc.resolve_invoke_model(parent.model_config)
    usage_sink = svc.chat_usage_sink(model, source_id=parent.id)
    raw = await ainvoke_chat(
        model,
        [{"role": "user", "content": prompt}],
        temperature=0.2,
        usage_sink=usage_sink,
    )
    plan = _parse_plan(raw)
    if plan:
        return plan
    return [{"sub_agent_id": str(bindings[0].child_agent_id), "task": query}]


async def _run_platform_planned(
    svc: AgentService,
    parent: Agent,
    bindings: list[AgentSubAgentBinding],
    body: ChatRequest,
) -> ChatResponse:
    """按规划依次 chat_as_child，最后主模型综合子回答。"""
    steps: list[dict] = [
        {
            "type": "planner",
            "engine": AgentPlanner.PLATFORM.value,
            "mode": "json_plan",
        }
    ]
    allowed = {str(b.child_agent_id) for b in bindings}
    plan = await _platform_plan(parent, bindings, body.query, svc=svc)
    steps.append({"type": "plan", "steps": plan})

    parallel = bool((parent.config or {}).get("subagent_parallel", False))
    max_calls = int((parent.config or {}).get("max_subagent_calls", 20))
    items = plan[:max_calls]

    async def run_one(item: dict) -> tuple[dict, str | None]:
        sid = item.get("sub_agent_id", "")
        if sid not in allowed:
            return (
                {"type": "subagent_skip", "reason": "非法子智能体 ID", "sub_agent_id": sid},
                None,
            )
        task = item.get("task", body.query)
        child_resp = await svc.chat_as_child(UUID(sid), ChatRequest(query=task, inputs=body.inputs))
        binding = next((b for b in bindings if str(b.child_agent_id) == sid), None)
        name = binding.child_agent.name if binding and binding.child_agent else sid
        step = {
            "type": "subagent",
            "sub_agent_id": sid,
            "sub_agent_name": name,
            "role_hint": binding.role_hint if binding else None,
            "task": task[:300],
            "output_preview": child_resp.answer[:500],
        }
        return step, f"【{name}】\n{child_resp.answer}"

    sub_answers: list[str] = []
    if parallel and len(items) > 1:
        results = await asyncio.gather(*[run_one(it) for it in items])
        for step, block in results:
            steps.append(step)
            if block:
                sub_answers.append(block)
    else:
        for item in items:
            step, block = await run_one(item)
            steps.append(step)
            if block:
                sub_answers.append(block)

    if not sub_answers:
        return ChatResponse(
            answer="未能委派子智能体完成任务，请检查绑定与模型配置。",
            sources=[],
            steps=steps,
        )

    if parent.model_config:
        synth_prompt = (
            f"{await svc.resolve_system_prompt(parent)}\n\n"
            f"用户问题：{body.query}\n\n"
            "各子智能体结果：\n" + "\n\n---\n\n".join(sub_answers) + "\n\n请综合以上结果，给用户一个完整、简洁的最终回答。"
        )
        model = await svc.resolve_invoke_model(parent.model_config)
        usage_sink = svc.chat_usage_sink(model, source_id=parent.id)
        final = await ainvoke_chat(
            model,
            [{"role": "user", "content": synth_prompt}],
            temperature=float((parent.config or {}).get("temperature", 0.7)),
            usage_sink=usage_sink,
        )
    else:
        final = "\n\n---\n\n".join(sub_answers)

    return ChatResponse(answer=final, sources=[], steps=steps)


def _should_use_deepagents(parent: Agent) -> bool:
    """是否启用 DeepAgents 库（非 force_platform_planner）。"""
    cfg = parent.config or {}
    if cfg.get("planner", AgentPlanner.DEEPAGENTS.value) != AgentPlanner.DEEPAGENTS.value:
        return False
    if cfg.get("force_platform_planner"):
        return False
    return deepagents_importable()


async def run_subagent_planned_chat(
    svc: AgentService,
    parent: Agent,
    bindings: list[AgentSubAgentBinding],
    body: ChatRequest,
) -> ChatResponse:
    """有子智能体绑定时，由 DeepAgents 或平台规划器拆解并委派子智能体。"""
    if _should_use_deepagents(parent) and parent.model_config:
        try:
            return await run_deepagents_chat(svc, parent, bindings, body)
        except Exception as exc:
            steps = [
                {
                    "type": "planner_fallback",
                    "engine": AgentPlanner.PLATFORM.value,
                    "error": str(exc)[:300],
                }
            ]
            resp = await _run_platform_planned(svc, parent, bindings, body)
            resp.steps = steps + resp.steps
            return resp

    return await _run_platform_planned(svc, parent, bindings, body)
