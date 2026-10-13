"""
自定义智能体调用外部 A2A Peer（与本地 RAG 可组合）。

入口与 RAG 关系
---------------
- ``run_a2a_augmented_chat``：**先** ``AgentService._rag_chat``（本地 KB 检索+生成），
  **再** ``augment_response_with_a2a`` 调外部 Peer 并可选 LLM 综合
- ``augment_response_with_a2a``：已有 ``ChatResponse`` 时仅做 A2A 增强（子 Agent 路径后）
- ``run_a2a_host_chat``：``agent_type=a2a`` 宿主，**不走**本地 KB/流程，仅编排外部 Peer

策略 ``config.a2a_invoke_policy``：``rules_only`` | ``rules_then_plan`` | ``plan_only``。
可选 ``config.a2a_intent_router.enabled``：规划阶段改用意图路由 LLM（见 ``intent_router``）。

子模块：``rules`` / ``plan`` / ``execute`` / ``chat``；本包为稳定 import 与单测
``monkeypatch.setattr(invoke_mod, …)`` 门面。
"""

from __future__ import annotations

from miles_integrations.langchain.chat_models import ainvoke_chat
from miles_portal.tenant.a2a.intent_router import intent_router_enabled, route_a2a_peers_by_intent
from miles_portal.tenant.a2a.invoke.chat import (
    augment_response_with_a2a,
    run_a2a_augmented_chat,
    run_a2a_host_chat,
)
from miles_portal.tenant.a2a.invoke.execute import execute_a2a_calls
from miles_portal.tenant.a2a.invoke.plan import (
    _parse_a2a_plan,
    _peer_catalog,
    plan_a2a_peers,
    resolve_a2a_plan_items,
)
from miles_portal.tenant.a2a.invoke.rules import (
    build_rule_plan_items,
    evaluate_rule_triggered_peers,
)
from miles_portal.tenant.a2a.services.host_bindings import list_host_peer_bindings
from miles_portal.tenant.a2a.services.peer_refs import list_agent_a2a_peer_refs
from miles_portal.tenant.agents.services.chat_memory import format_history_block, load_chat_history_messages
from miles_portal.tenant.agents.services.user_memory import UserMemoryService
from miles_portal.tenant.models.services.model_resolve import resolve_model_for_invoke
from miles_portal.tenant.models.services.usage import ChatUsageSink

__all__ = [
    "ChatUsageSink",
    "UserMemoryService",
    "_parse_a2a_plan",
    "_peer_catalog",
    "ainvoke_chat",
    "augment_response_with_a2a",
    "build_rule_plan_items",
    "evaluate_rule_triggered_peers",
    "execute_a2a_calls",
    "format_history_block",
    "intent_router_enabled",
    "list_agent_a2a_peer_refs",
    "list_host_peer_bindings",
    "load_chat_history_messages",
    "plan_a2a_peers",
    "resolve_a2a_plan_items",
    "resolve_model_for_invoke",
    "route_a2a_peers_by_intent",
    "run_a2a_augmented_chat",
    "run_a2a_host_chat",
]
