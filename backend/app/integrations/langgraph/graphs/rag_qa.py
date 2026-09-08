"""
RAG 问答 LangGraph（Agent 默认 RAG 引擎）。

节点流
------
START → retrieve（``retrieve_hits`` 多 KB；仅用 ``query`` 文本，不用附图）
     → grade_documents（分数阈值或 LLM 评判 good/poor/none）
     → route_after_grade
         - good → generate（``build_rag_user_prompt`` + ``ainvoke_chat``，可带 media）
         - poor → prepare_retry（top_k×2，≤20）→ retrieve
         - none / 重试耗尽 → fallback（低相关或无命中话术）

``query`` 用于检索；``prompt_query`` 写入生成 prompt（Agent 附图场景可与 query 不同）。

状态字段见 ``integrations.langgraph.state.RAGGraphState``；
``agent.config`` 可设 ``rag_max_retries``、``relevance_threshold``、``use_llm_grade``。
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.core.tenant import TenantContext
from app.integrations.chat.multimodal import (
    build_invoke_messages_with_media,
    media_refs_from_items,
)
from app.integrations.langchain.chat_models import ainvoke_chat
from app.rag.generate import build_rag_user_prompt, format_hits_context, retrieve_hits
from app.infra.db import AsyncSessionLocal
from app.integrations.langgraph.constants import RELEVANCE_NONE, RELEVANCE_POOR
from app.integrations.langgraph.grading import _score_grade, llm_grade_relevance
from app.integrations.langgraph.state import RAGGraphState
from app.models.model import ModelConfig


def _tenant_from_state(state: RAGGraphState) -> TenantContext:
    """RAG 图内解析附件需租户 user_id（由 run_rag_workflow 注入）。"""
    uid = state.get("user_id")
    if not uid:
        raise ValueError("RAG 状态缺少 user_id，无法解析附图")
    return TenantContext(
        user_id=UUID(uid),
        tenant_id=UUID(state["tenant_id"]),
        username="rag-graph",
        is_superuser=False,
        permissions=frozenset(),
    )


def _cfg_model(config: RunnableConfig | None) -> ModelConfig:
    """从 RunnableConfig.configurable 取已 resolve 的 ModelConfig。"""
    if not config or "configurable" not in config:
        raise ValueError("LangGraph 缺少 configurable.model")
    model = config["configurable"].get("model")  # type: ignore[union-attr]
    if not model:
        raise ValueError("LangGraph 缺少 model 配置")
    return model


async def retrieve(state: RAGGraphState, config: RunnableConfig) -> dict[str, Any]:
    """节点：多 KB retrieve_hits，写入 hits 与 steps（仅用文本 query，不用附图）。"""
    tenant_id = UUID(state["tenant_id"])
    search_q = (state.get("query") or "").strip()
    async with AsyncSessionLocal() as db:
        hits = await retrieve_hits(
            search_q,
            tenant_id=tenant_id,
            kb_ids=state["kb_ids"],
            db=db,
            top_k=state.get("top_k", 5),
        )
    return {
        "hits": hits,
        "steps": [
            {
                "type": "retrieve",
                "node": "retrieve",
                "retry_count": state.get("retry_count", 0),
                "hit_count": len(hits),
                "top_score": max((h.get("score", 0) for h in hits), default=0),
            }
        ],
    }


async def grade_documents(state: RAGGraphState, config: RunnableConfig) -> dict[str, Any]:
    """节点：按分数或 LLM 评判检索相关性（good/poor/none）。"""
    hits = state.get("hits") or []
    threshold = float(state.get("relevance_threshold", 0.35))
    relevance, top_score = _score_grade(hits, threshold)
    grade_method = "score"
    reason = ""

    if state.get("use_llm_grade") and hits:
        try:
            model = _cfg_model(config)
            llm_rel, reason = await llm_grade_relevance(
                model,
                query=state["query"],
                hits=hits,
            )
            if llm_rel:
                relevance = llm_rel
                grade_method = "llm"
        except Exception as exc:
            grade_method = "score_fallback"
            reason = str(exc)[:200]

    return {
        "relevance": relevance,
        "steps": [
            {
                "type": "grade",
                "node": "grade_documents",
                "relevance": relevance,
                "top_score": top_score,
                "threshold": threshold,
                "grade_method": grade_method,
                "reason": reason[:300] if reason else None,
            }
        ],
    }


def route_after_grade(state: RAGGraphState) -> Literal["generate", "retry", "fallback"]:
    """poor 且未超重试次数 → 扩大 top_k 再检索；none → 无依据兜底话术。"""
    relevance = state.get("relevance", RELEVANCE_NONE)
    retry_count = int(state.get("retry_count", 0))
    max_retries = int(state.get("max_retries", 1))

    if relevance == RELEVANCE_NONE:
        return "fallback"
    if relevance == RELEVANCE_POOR:
        if retry_count < max_retries:
            return "retry"
        return "fallback"
    return "generate"


async def prepare_retry(state: RAGGraphState) -> dict[str, Any]:
    """节点：扩大 top_k 后回到 retrieve 重试。"""
    new_retry = int(state.get("retry_count", 0)) + 1
    new_top_k = min(int(state.get("top_k", 5)) * 2, 20)
    return {
        "retry_count": new_retry,
        "top_k": new_top_k,
        "steps": [
            {
                "type": "retry",
                "node": "prepare_retry",
                "retry_count": new_retry,
                "top_k": new_top_k,
            }
        ],
    }


def _prompt_user_query(state: RAGGraphState) -> str:
    """生成阶段用户问题：优先 prompt_query，否则 query。"""
    return (state.get("prompt_query") or state.get("query") or "").strip()


async def generate(state: RAGGraphState, config: RunnableConfig) -> dict[str, Any]:
    """节点：有相关命中时正常 RAG 生成答案（生成阶段可带附图）。"""
    model = _cfg_model(config)
    hits = state.get("hits") or []
    user_q = _prompt_user_query(state)
    if hits:
        prompt = build_rag_user_prompt(
            system_prompt=state["system_prompt"],
            query=user_q,
            hits=hits,
        )
    else:
        prompt = f"{state['system_prompt']}\n\n用户问题：{user_q}"

    media_refs = media_refs_from_items(state.get("media"))
    async with AsyncSessionLocal() as db:
        try:
            tenant_ctx = _tenant_from_state(state)
        except ValueError:
            tenant_ctx = None
        if media_refs and tenant_ctx:
            messages = await build_invoke_messages_with_media(
                db,
                tenant_ctx,
                prompt_text=prompt,
                media=media_refs,
            )
        else:
            messages = [{"role": "user", "content": prompt}]
        on_delta = config.get("configurable", {}).get("on_delta") if config else None
        usage_sink = config["configurable"].get("usage_sink") if config else None
        answer = await ainvoke_chat(
            model,
            messages,
            temperature=float(state.get("temperature", 0.7)),
            usage_sink=usage_sink,
            on_delta=on_delta,
        )
    return {
        "answer": answer,
        "steps": [
            {
                "type": "generate",
                "node": "generate",
                "hit_count": len(hits),
                "answer_preview": answer[:300],
            }
        ],
    }


async def fallback(state: RAGGraphState, config: RunnableConfig) -> dict[str, Any]:
    """节点：无命中或相关性差时的保守回答话术（生成阶段可带附图）。"""
    model = _cfg_model(config)
    hits = state.get("hits") or []
    if hits:
        context = format_hits_context(hits)
        prompt = (
            f"{state['system_prompt']}\n\n检索到的内容相关性较低，请谨慎回答并说明依据有限。\n\n参考片段：\n{context}\n\n用户问题：{_prompt_user_query(state)}"
        )
    else:
        prompt = (
            f"{state['system_prompt']}\n\n"
            f"知识库中未检索到与问题直接相关的内容。请基于通用知识简要回答，"
            f"并明确说明未命中企业知识库。\n\n用户问题：{_prompt_user_query(state)}"
        )
    media_refs = media_refs_from_items(state.get("media"))
    async with AsyncSessionLocal() as db:
        try:
            tenant_ctx = _tenant_from_state(state)
        except ValueError:
            tenant_ctx = None
        if media_refs and tenant_ctx:
            messages = await build_invoke_messages_with_media(
                db,
                tenant_ctx,
                prompt_text=prompt,
                media=media_refs,
            )
        else:
            messages = [{"role": "user", "content": prompt}]
        on_delta = config.get("configurable", {}).get("on_delta") if config else None
        usage_sink = config["configurable"].get("usage_sink") if config else None
        answer = await ainvoke_chat(
            model,
            messages,
            temperature=float(state.get("temperature", 0.7)),
            usage_sink=usage_sink,
            on_delta=on_delta,
        )
    return {
        "answer": answer,
        "steps": [
            {
                "type": "fallback",
                "node": "fallback",
                "hit_count": len(hits),
                "relevance": state.get("relevance"),
            }
        ],
    }


def build_rag_qa_graph():
    """编译前 StateGraph：retrieve → grade → generate|retry|fallback（不含 checkpointer）。"""
    graph = StateGraph(RAGGraphState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("grade_documents", grade_documents)
    graph.add_node("prepare_retry", prepare_retry)
    graph.add_node("generate", generate)
    graph.add_node("fallback", fallback)

    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "grade_documents")
    graph.add_conditional_edges(
        "grade_documents",
        route_after_grade,
        {
            "generate": "generate",
            "retry": "prepare_retry",
            "fallback": "fallback",
        },
    )
    graph.add_edge("prepare_retry", "retrieve")
    graph.add_edge("generate", END)
    graph.add_edge("fallback", END)
    return graph
