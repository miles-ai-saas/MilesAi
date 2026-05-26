"""知识库枚举展示元数据（GET /kb/meta）。

- retrieval_modes / search_modes / search_sources / document_statuses
- 前端：lib/kb-labels.ts、hooks/use-kb-meta.ts
- 约定：docs/guides/hooks.md §9
"""

from app.common.schemas.enum_meta import literal_options

RETRIEVAL_MODE_OPTIONS: list[tuple[str, str, str | None]] = [
    ("vector", "纯语义向量", "基于 embedding 相似度"),
    ("hybrid", "混合检索", "向量 + 关键词（BM25 等）"),
]

SEARCH_MODE_OPTIONS: list[tuple[str, str, str | None]] = [
    ("default", "跟随知识库", "使用知识库配置的 retrieval_mode"),
    ("vector", "纯语义向量", "单次检索覆盖"),
    ("hybrid", "混合检索", "单次检索覆盖"),
]

SEARCH_SOURCE_OPTIONS: list[tuple[str, str, str | None]] = [
    ("api", "API 调试", None),
    ("agent", "智能体 RAG", None),
    ("flow", "流程", None),
    ("debug", "调试", None),
]

DOCUMENT_STATUS_OPTIONS: list[tuple[str, str, str | None]] = [
    ("pending", "待处理", None),
    ("parsing", "解析中", None),
    ("embedding", "向量化中", None),
    ("ready", "就绪", None),
    ("parse_failed", "解析失败", None),
    ("embed_failed", "向量化失败", None),
]


def kb_meta_dict() -> dict:
    """构建 meta 响应 dict，供 *MetaOut.model_validate 与单测使用。"""
    return {
        "retrieval_modes": literal_options(RETRIEVAL_MODE_OPTIONS),
        "search_modes": literal_options(SEARCH_MODE_OPTIONS),
        "search_sources": literal_options(SEARCH_SOURCE_OPTIONS),
        "document_statuses": literal_options(DOCUMENT_STATUS_OPTIONS),
    }
