"""对话主路径独立意图识别层。

在合规之后、五条路由分发之前调用一次结构化 LLM，输出
``direct`` / ``rag`` / ``tools`` / ``flow`` / ``subagent`` / ``a2a`` / ``auto``。
配置：``agent.config.chat_intent_router.enabled``（默认关闭，不影响现网路由）。
与 A2A 专用 ``a2a_intent_router`` 解耦：本层决定顶层路由，A2A 层仍只管 peer。
"""

from __future__ import annotations

import json
import re
import time
from typing import Any
from uuid import UUID

from miles_core.logging import get_logger
from miles_core.models.agent import Agent
from miles_core.models.model import ModelConfig
from miles_integrations.langchain.chat_models import ainvoke_chat
from miles_portal.tenant.models.services.model_resolve import resolve_model_for_invoke
from miles_portal.tenant.models.services.usage import ChatUsageSink

logger = get_logger(__name__)

#: 意图枚举（与路由能力对齐）。
CHAT_INTENTS = frozenset({"auto", "direct", "rag", "tools", "flow", "subagent", "a2a"})

_JSON_RE = re.compile(r"\{[\s\S]*\}")


def chat_intent_router_enabled(agent: Agent) -> bool:
    """``config.chat_intent_router.enabled`` 为真时启用顶层意图识别。"""
    cfg = (agent.config or {}).get("chat_intent_router")
    if not isinstance(cfg, dict):
        return False
    return bool(cfg.get("enabled"))


def chat_intent_router_config(agent: Agent) -> dict[str, Any]:
    """规范化意图路由配置。"""
    raw = (agent.config or {}).get("chat_intent_router")
    if not isinstance(raw, dict):
        return {"enabled": False, "model_config_id": None}
    mid = raw.get("model_config_id")
    return {
        "enabled": bool(raw.get("enabled")),
        "model_config_id": str(mid).strip() if mid else None,
    }


def build_capability_catalog(
    *,
    has_model: bool,
    has_kb: bool,
    tools_enabled: bool,
    has_flow: bool,
    has_subagents: bool,
    has_a2a_peers: bool,
) -> list[dict[str, str]]:
    """根据智能体当前绑定生成可选意图目录。"""
    items: list[dict[str, str]] = []
    if has_model:
        items.append({"intent": "direct", "desc": "无需检索/工具/委派，直接由本智能体模型回答"})
    if has_kb:
        items.append({"intent": "rag", "desc": "需要查询本智能体绑定的知识库"})
    if tools_enabled:
        items.append({"intent": "tools", "desc": "需要调用平台工具 / MCP / 生成式工具"})
    if has_flow:
        items.append({"intent": "flow", "desc": "适合走已发布的可视化流程编排"})
    if has_subagents:
        items.append({"intent": "subagent", "desc": "需要拆解任务并委派给绑定的子智能体"})
    if has_a2a_peers:
        items.append({"intent": "a2a", "desc": "需要调用已登记的外部 A2A 智能体"})
    items.append({"intent": "auto", "desc": "不确定时选此项，交由系统默认优先级路由"})
    return items


def parse_chat_intent(raw: str) -> tuple[str, str | None]:
    """解析 LLM 输出为 ``(intent, reason)``；非法时回落 ``auto``。"""
    text = (raw or "").strip()
    if not text:
        return "auto", None
    m = _JSON_RE.search(text)
    blob = m.group(0) if m else text
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        return "auto", None
    if not isinstance(data, dict):
        return "auto", None
    intent = str(data.get("intent") or "auto").strip().lower()
    if intent not in CHAT_INTENTS:
        intent = "auto"
    reason = data.get("reason")
    reason_s = str(reason).strip() if reason is not None else None
    return intent, reason_s or None


def pick_top_level_route(
    *,
    preferred: str | None,
    has_bindings: bool,
    has_peer_refs: bool,
) -> str:
    """将意图映射为顶层路由闸：``subagent`` | ``a2a_augmented`` | ``local``。

    ``local`` 表示走流程/RAG/工具/直连分支（不再强制进子智能体或 A2A 增强）。
    """
    pref = (preferred or "auto").lower()
    if pref == "subagent" and has_bindings:
        return "subagent"
    if pref == "a2a" and has_peer_refs:
        return "a2a_augmented"
    if pref in ("flow", "tools", "rag", "direct"):
        return "local"
    if has_bindings:
        return "subagent"
    if has_peer_refs:
        return "a2a_augmented"
    return "local"


def should_skip_published_flow(preferred: str | None) -> bool:
    """意图明确要本地直连/检索/工具时，跳过「有流程就先跑流程」的默认优先级。"""
    return (preferred or "").lower() in ("tools", "rag", "direct")


async def recognize_chat_intent(
    agent: Agent,
    query: str,
    *,
    catalog: list[dict[str, str]],
    db: Any,
    tenant_id: UUID,
    model_override: ModelConfig | None = None,
) -> tuple[str, dict[str, Any]]:
    """调用 LLM 识别意图；返回 ``(intent, step_meta)``。

    失败 / 无模型 / 空目录时 intent=``auto``，不抛错（回落默认路由）。
    """
    started = time.perf_counter()
    meta: dict[str, Any] = {
        "engine": "intent_llm",
        "intent": "auto",
        "reason": None,
        "latency_ms": 0,
        "empty_reason": None,
        "available": [c["intent"] for c in catalog if c["intent"] != "auto"],
    }
    allowed = {c["intent"] for c in catalog}
    model_row = model_override or agent.model_config
    if model_row is None:
        meta["empty_reason"] = "no_model"
        meta["latency_ms"] = int((time.perf_counter() - started) * 1000)
        return "auto", meta
    if len(allowed) <= 1:
        meta["empty_reason"] = "no_capabilities"
        meta["latency_ms"] = int((time.perf_counter() - started) * 1000)
        return "auto", meta

    lines = "\n".join(f"- {c['intent']}: {c['desc']}" for c in catalog)
    prompt = (
        "你是企业智能体的意图识别器。根据用户问题，从下列「可用能力」中选一个 intent。\n"
        "规则：\n"
        "1. 只输出 JSON：{\"intent\":\"...\",\"reason\":\"一句话理由\"}。\n"
        "2. intent 必须是目录中的值；不确定时用 auto。\n"
        "3. 不要编造目录外的 intent。\n"
        f"可用能力：\n{lines}\n\n用户问题：{query}"
    )
    try:
        model = await resolve_model_for_invoke(db, model_row, tenant_id)
        usage_sink = ChatUsageSink(tenant_id=tenant_id, model=model, source_id=agent.id)
        if db is not None:
            await db.commit()
        raw = await ainvoke_chat(
            model,
            [{"role": "user", "content": prompt}],
            temperature=0.1,
            usage_sink=usage_sink,
        )
        intent, reason = parse_chat_intent(raw)
        if intent not in allowed:
            meta["empty_reason"] = "invalid_intent"
            intent = "auto"
        meta["intent"] = intent
        meta["reason"] = reason
    except Exception:
        logger.debug("chat intent recognize failed agent_id=%s", getattr(agent, "id", None), exc_info=True)
        meta["empty_reason"] = "llm_error"
        intent = "auto"
    meta["latency_ms"] = int((time.perf_counter() - started) * 1000)
    return intent, meta


async def resolve_intent_model(
    db: Any,
    agent: Agent,
    *,
    tenant_id: UUID,
) -> ModelConfig | None:
    """解析意图识别所用模型：优先配置的 ``model_config_id``，否则主模型。"""
    cfg = chat_intent_router_config(agent)
    mid = cfg.get("model_config_id")
    if mid:
        try:
            uid = UUID(str(mid))
        except ValueError:
            uid = None
        if uid is not None:
            row = await db.get(ModelConfig, uid)
            if row is not None:
                return row
    return agent.model_config
