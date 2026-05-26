"""知识库枚举展示元数据（GET /kb/meta）。

- retrieval_modes / search_modes / search_sources / document_statuses
- 前端：lib/kb-labels.ts、hooks/use-kb-meta.ts
- 约定：docs/guides/hooks.md §9
"""

from app.common.schemas.enum_meta import META_SCHEMA_VERSION, enum_options, literal_options
from app.models.kb import DocumentStatus
from app.rag.retrieve.constants import RETRIEVAL_HYBRID, RETRIEVAL_VECTOR

RETRIEVAL_MODE_OPTIONS: list[tuple[str, str, str | None]] = [
    (RETRIEVAL_VECTOR, "纯语义向量", "基于 embedding 相似度"),
    (RETRIEVAL_HYBRID, "混合检索", "向量 + 关键词（BM25 等）"),
]

SEARCH_MODE_DEFAULT = "default"

SEARCH_MODE_OPTIONS: list[tuple[str, str, str | None]] = [
    (SEARCH_MODE_DEFAULT, "跟随知识库", "使用知识库配置的 retrieval_mode"),
    (RETRIEVAL_VECTOR, "纯语义向量", "单次检索覆盖"),
    (RETRIEVAL_HYBRID, "混合检索", "单次检索覆盖"),
]

SEARCH_SOURCE_OPTIONS: list[tuple[str, str, str | None]] = [
    ("api", "API 调试", None),
    ("agent", "智能体 RAG", None),
    ("flow", "流程", None),
    ("debug", "调试", None),
]

DOCUMENT_STATUS_LABELS: dict[str, tuple[str, str | None]] = {
    DocumentStatus.PENDING.value: ("待处理", None),
    DocumentStatus.PARSING.value: ("解析中", None),
    DocumentStatus.EMBEDDING.value: ("向量化中", None),
    DocumentStatus.READY.value: ("就绪", None),
    DocumentStatus.PARSE_FAILED.value: ("解析失败", None),
    DocumentStatus.EMBED_FAILED.value: ("向量化失败", None),
}


def kb_meta_dict() -> dict:
    """构建 meta 响应 dict，供 *MetaOut.model_validate 与单测使用。"""
    return {
        "retrieval_modes": literal_options(RETRIEVAL_MODE_OPTIONS),
        "search_modes": literal_options(SEARCH_MODE_OPTIONS),
        "search_sources": literal_options(SEARCH_SOURCE_OPTIONS),
        "document_statuses": enum_options(DocumentStatus, DOCUMENT_STATUS_LABELS),
        "schema_version": META_SCHEMA_VERSION,
    }
