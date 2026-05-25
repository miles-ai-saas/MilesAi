"""RAG 相关性标签（LangGraph grade_documents 与 route_after_grade）。"""

RELEVANCE_GOOD = "good"  # 可支撑回答
RELEVANCE_POOR = "poor"  # 相关不足，可重试扩大 top_k
RELEVANCE_NONE = "none"  # 无有效命中，走 fallback
