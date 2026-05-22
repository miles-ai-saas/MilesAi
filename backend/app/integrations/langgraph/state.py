"""LangGraph 状态定义。"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class RAGGraphState(TypedDict, total=False):
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
