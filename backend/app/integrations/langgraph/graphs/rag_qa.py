"""RAG 问答 LangGraph：检索 → 质量评估 → 重试 / 生成 / 兜底。"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.integrations.langchain.chat_models import ainvoke_chat
from app.rag.generate import build_rag_user_prompt, format_hits_context, retrieve_hits
from app.infra.db import AsyncSessionLocal
from app.integrations.langgraph.constants import RELEVANCE_GOOD, RELEVANCE_NONE, RELEVANCE_POOR
from app.integrations.langgraph.grading import _score_grade, llm_grade_relevance
from app.integrations.langgraph.state import RAGGraphState
from app.models.model import ModelConfig


def _cfg_model(config: RunnableConfig | None) -> ModelConfig:
    if not config or "configurable" not in config:
        raise ValueError("LangGraph 缺少 configurable.model")
    model = config["configurable"].get("model")  # type: ignore[union-attr]
    if not model:
        raise ValueError("LangGraph 缺少 model 配置")
    return model


async def retrieve(state: RAGGraphState, config: RunnableConfig) -> dict[str, Any]:
    tenant_id = UUID(state["tenant_id"])
    async with AsyncSessionLocal() as db:
        hits = await retrieve_hits(
            state["query"],
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


async def generate(state: RAGGraphState, config: RunnableConfig) -> dict[str, Any]:
    model = _cfg_model(config)
    hits = state.get("hits") or []
    if hits:
        prompt = build_rag_user_prompt(
            system_prompt=state["system_prompt"],
            query=state["query"],
            hits=hits,
        )
    else:
        prompt = f"{state['system_prompt']}\n\n用户问题：{state['query']}"

    answer = await ainvoke_chat(
        model,
        [{"role": "user", "content": prompt}],
        temperature=float(state.get("temperature", 0.7)),
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
    model = _cfg_model(config)
    hits = state.get("hits") or []
    if hits:
        context = format_hits_context(hits)
        prompt = (
            f"{state['system_prompt']}\n\n"
            f"检索到的内容相关性较低，请谨慎回答并说明依据有限。\n\n"
            f"参考片段：\n{context}\n\n用户问题：{state['query']}"
        )
    else:
        prompt = (
            f"{state['system_prompt']}\n\n"
            f"知识库中未检索到与问题直接相关的内容。请基于通用知识简要回答，"
            f"并明确说明未命中企业知识库。\n\n用户问题：{state['query']}"
        )
    answer = await ainvoke_chat(
        model,
        [{"role": "user", "content": prompt}],
        temperature=float(state.get("temperature", 0.7)),
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
