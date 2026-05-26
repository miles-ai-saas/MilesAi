"""
RAG 相关性三态标签（``grade_documents`` → ``route_after_grade``）。

- ``good``：top 分数 ≥ threshold，走正常 generate
- ``poor``：有命中但分数低，可扩大 top_k 重试
- ``none``：无命中，走 fallback 保守话术
"""

RELEVANCE_GOOD = "good"  # 可支撑回答
RELEVANCE_POOR = "poor"  # 相关不足，可重试扩大 top_k
RELEVANCE_NONE = "none"  # 无有效命中，走 fallback

GRADE_BRANCH_HANDLES = frozenset({RELEVANCE_GOOD, RELEVANCE_POOR, RELEVANCE_NONE})
