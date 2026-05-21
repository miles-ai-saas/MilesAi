"""LangGraph 运行入口。"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langgraph.checkpoint.memory import MemorySaver

from app.ai_stack.langgraph.checkpointer import checkpoint_backend, get_compiled_rag_graph
from app.ai_stack.langgraph.graphs.rag_qa import build_rag_qa_graph
from app.models.agent import Agent
from app.models.model import ModelConfig


def should_use_langgraph_rag(agent: Agent, *, kb_ids: list[str]) -> bool:
    if not kb_ids:
        return False
    cfg = agent.config or {}
    if cfg.get("runtime_mode") == "legacy":
        return False
    if cfg.get("runtime_mode") == "autonomous":
        return False
    if cfg.get("use_langgraph_rag") is False:
        return False
    return True


def build_rag_thread_id(
    *,
    tenant_id: UUID,
    agent_id: UUID,
    conversation_id: str | None = None,
) -> str:
    suffix = (conversation_id or "default").strip()[:128] or "default"
    return f"{tenant_id}:{agent_id}:{suffix}"


async def run_rag_workflow(
    *,
    model: ModelConfig,
    system_prompt: str,
    query: str,
    kb_ids: list[str],
    tenant_id: UUID,
    agent_id: UUID,
    top_k: int = 5,
    temperature: float = 0.7,
    thread_id: str | None = None,
    conversation_id: str | None = None,
    agent_config: dict | None = None,
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    """执行 RAG LangGraph，返回 (answer, hits, steps)。"""
    graph = get_compiled_rag_graph()
    cfg = agent_config or {}
    tid = thread_id or build_rag_thread_id(
        tenant_id=tenant_id,
        agent_id=agent_id,
        conversation_id=conversation_id,
    )
    initial: dict[str, Any] = {
        "query": query,
        "system_prompt": system_prompt,
        "kb_ids": kb_ids,
        "tenant_id": str(tenant_id),
        "top_k": top_k,
        "temperature": temperature,
        "max_retries": int(cfg.get("rag_max_retries", 1)),
        "retry_count": 0,
        "relevance_threshold": float(cfg.get("relevance_threshold", 0.35)),
        "use_llm_grade": bool(cfg.get("use_llm_grade", False)),
        "hits": [],
        "steps": [
            {
                "type": "graph_start",
                "engine": "langgraph",
                "checkpointer": checkpoint_backend(),
                "thread_id": tid,
            }
        ],
    }
    run_config = {
        "configurable": {
            "thread_id": tid,
            "model": model,
        }
    }
    final = await graph.ainvoke(initial, run_config)
    return (
        final.get("answer") or "",
        final.get("hits") or [],
        final.get("steps") or [],
    )


def compile_rag_graph_for_tests():
    """测试环境未走 lifespan 时编译图。"""
    return build_rag_qa_graph().compile(checkpointer=MemorySaver())
