"""
LangGraph 运行入口（Agent RAG）。

RAG 图
------
``build_rag_qa_graph``：retrieve → grade → generate | retry | fallback。
编译实例由 ``get_compiled_rag_graph()`` 提供，checkpointer 见 ``checkpointer`` 模块。

``should_use_langgraph_rag`` 关闭条件（``agent.config``）
-------------------------------------------------------
- 无绑定 KB
- ``runtime_mode`` 为 ``legacy`` / ``autonomous``
- ``use_langgraph_rag: false``

否则默认走 LangGraph；线性路径见 ``rag.generate.rag_answer``。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langgraph.checkpoint.memory import MemorySaver

from app.integrations.langchain.chat_models import OnDelta
from app.integrations.langchain.kb_retrieval import KbRetrievalBindings
from app.integrations.langgraph.checkpointer import checkpoint_backend, get_compiled_rag_graph
from app.integrations.langgraph.graphs.rag_qa import build_rag_qa_graph
from app.integrations.litellm.usage_sink import UsageSink
from app.common.schemas.media import MediaRefIn
from app.models.agent import Agent
from app.models.agent.constants import AgentRuntimeMode
from app.models.media.reader import MediaReader
from app.models.model import ModelConfig


def should_use_langgraph_rag(agent: Agent, *, kb_ids: list[str]) -> bool:
    """有 KB 且未显式关闭时默认 True（LangGraph 带相关性评分与重试）。"""
    if not kb_ids:
        return False
    cfg = agent.config or {}
    if cfg.get("runtime_mode") == AgentRuntimeMode.LEGACY.value:
        return False
    if cfg.get("runtime_mode") == AgentRuntimeMode.AUTONOMOUS.value:
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
    """LangGraph checkpointer 线程 id，隔离租户/智能体/会话。"""
    suffix = (conversation_id or "default").strip()[:128] or "default"
    return f"{tenant_id}:{agent_id}:{suffix}"


async def run_rag_workflow(
    *,
    model: ModelConfig,
    system_prompt: str,
    query: str,
    prompt_query: str | None = None,
    kb_ids: list[str],
    tenant_id: UUID,
    agent_id: UUID,
    top_k: int = 5,
    temperature: float = 0.7,
    thread_id: str | None = None,
    conversation_id: str | None = None,
    agent_config: dict | None = None,
    media: list[MediaRefIn] | None = None,
    user_id: UUID | None = None,
    on_delta: OnDelta | None = None,
    usage_sink: UsageSink | None = None,
    bindings: KbRetrievalBindings | None = None,
    media_reader: MediaReader | None = None,
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    """执行 RAG LangGraph，返回 (answer, hits, steps)。

    ``model`` 由调用方 resolve（装配点语义，见 ``resolve_invoke_model``），
    直接写入 ``configurable.model`` 供各节点 ``_cfg_model`` 读取；
    ``usage_sink`` 同写入 configurable，由 generate/fallback 透传给 ``ainvoke_chat``；
    ``bindings``（KB 检索绑定）同写入 configurable，由 retrieve 节点透传 ``retrieve_hits``；
    ``media_reader``（L1 注入的媒体读取器）写入 configurable，由 generate/fallback
    节点读取以解析附图。
    ``thread_id`` 写入 checkpointer。
    """
    graph = get_compiled_rag_graph()
    cfg = agent_config or {}
    tid = thread_id or build_rag_thread_id(
        tenant_id=tenant_id,
        agent_id=agent_id,
        conversation_id=conversation_id,
    )
    initial: dict[str, Any] = {
        "query": query,
        "prompt_query": (prompt_query or query).strip(),
        "system_prompt": system_prompt,
        "kb_ids": kb_ids,
        "tenant_id": str(tenant_id),
        "top_k": top_k,
        "temperature": temperature,
        "max_retries": int(cfg.get("rag_max_retries", 1)),
        "retry_count": 0,
        "relevance_threshold": float(cfg.get("relevance_threshold", 0.35)),
        "use_llm_grade": bool(cfg.get("use_llm_grade", False)),
        "media": [m.model_dump(mode="json") for m in (media or [])],
        "user_id": str(user_id) if user_id else "",
        "agent_id": str(agent_id),
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
            "on_delta": on_delta,
            "usage_sink": usage_sink,
            "kb_retrieval": bindings,
            "media_reader": media_reader,
        }
    }
    final = await graph.ainvoke(initial, run_config)
    return (
        final.get("answer") or "",
        final.get("hits") or [],
        final.get("steps") or [],
    )


def compile_rag_graph_for_tests():
    """测试环境未走 lifespan init_checkpointer 时编译内存图。"""
    return build_rag_qa_graph().compile(checkpointer=MemorySaver())
