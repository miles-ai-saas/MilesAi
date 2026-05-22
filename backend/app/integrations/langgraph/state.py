"""LangGraph 状态定义（RAG QA 图节点间传递的 TypedDict）。"""

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
