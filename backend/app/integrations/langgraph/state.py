"""
LangGraph RAG QA 图状态（节点间 TypedDict）。

``steps`` 使用 ``Annotated[..., operator.add]`` 累积各节点审计信息，供 ``ChatResponse.steps`` 展示。
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class RAGGraphState(TypedDict, total=False):
    """retrieve → grade → generate 链路；steps 用 operator.add 累积审计步骤。"""

    query: str
    system_prompt: str
    kb_ids: list[str]
    tenant_id: str
    top_k: int
    temperature: float
    max_retries: int
    retry_count: int
    relevance_threshold: float
    use_llm_grade: bool
    hits: list[dict[str, Any]]
    relevance: str
    answer: str
    steps: Annotated[list[dict[str, Any]], operator.add]
