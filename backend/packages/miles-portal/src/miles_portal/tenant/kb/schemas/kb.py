"""
知识库 HTTP 请求/响应模型（Pydantic）。

与 ORM 的对应关系
----------------
- ``KnowledgeBaseCreate/Update`` → ``models.kb.KnowledgeBase``
- ``DocumentOut`` → ``Document`` + 列表接口可选 ``chunk_count``
- ``SearchRequest/SearchHit`` → 检索 API；命中 ``content`` 来自 PG 分片，非向量库 preview

业务约束（校验在 schema 层）
----------------------------
- 创建 KB 时可指定 ``embedding_model_config_id``；**更新禁止**改 embedding 维度/模型（见 ``KnowledgeBaseUpdate`` validator）
- ``SearchMode.default`` 表示使用 KB 上配置的 ``retrieval_mode``
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from miles_ai.rag.retrieve.constants import RETRIEVAL_HYBRID, RETRIEVAL_VECTOR
from miles_core.models.kb import DocumentStatus
from miles_portal.tenant.kb.meta import SEARCH_MODE_DEFAULT

RetrievalMode = Literal[RETRIEVAL_VECTOR, RETRIEVAL_HYBRID]
SearchMode = Literal[SEARCH_MODE_DEFAULT, RETRIEVAL_VECTOR, RETRIEVAL_HYBRID]
MediaType = Literal["text", "image", "audio", "video"]


class KnowledgeBaseCreate(BaseModel):
    """创建知识库；未指定 embedding 时使用内置默认 BGE 并固化 ``embedding_dimension``。"""

    name: str = Field(..., min_length=1, max_length=128, description="知识库名称")
    description: str | None = Field(default=None, description="描述")
    is_public: bool = Field(default=False, description="是否公开")
    chunk_size: int = Field(500, ge=100, le=4000, description="分片大小（字符数）")
    chunk_overlap: int = Field(50, ge=0, le=500, description="分片重叠长度（字符数）")
    embedding_model_config_id: UUID | None = Field(
        None,
        description="向量化模型（model_type=embedding），默认内置 BGE；创建后不可修改",
    )
    visual_embedding_model_config_id: UUID | None = Field(
        None,
        description="CLIP 视觉向量化模型；配置后图片入库写入视觉向量，并支持 visual_search",
    )
    retrieval_mode: RetrievalMode = Field(
        RETRIEVAL_VECTOR,
        description="检索策略：vector=纯语义；hybrid=向量+关键词（Weaviate BM25 / Milvus+PG）",
    )
    hybrid_alpha: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="混合检索权重（仅 hybrid；1=偏向量，0=偏关键词，Weaviate 生效）",
    )
    rerank_model_config_id: UUID | None = Field(
        None,
        description="重排模型（model_type=rerank）；为空则不启用精排",
    )
    rerank_candidate_k: int = Field(
        50,
        ge=5,
        le=100,
        description="启用重排时，首轮召回候选数上限（再精排截断 top_k）",
    )


# 更新知识库入参；禁止修改 embedding 模型/维度（见 ``reject_embedding_changes``）。
class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(default=None, description="知识库名称")
    description: str | None = Field(default=None, description="描述")
    is_public: bool | None = Field(default=None, description="是否公开")
    chunk_size: int | None = Field(None, ge=100, le=4000, description="分片大小（字符数）")
    chunk_overlap: int | None = Field(None, ge=0, le=500, description="分片重叠长度（字符数）")
    retrieval_mode: RetrievalMode | None = Field(default=None, description="检索策略")
    hybrid_alpha: float | None = Field(None, ge=0.0, le=1.0, description="混合检索权重")
    rerank_model_config_id: UUID | None = Field(default=None, description="重排模型配置 ID")
    rerank_candidate_k: int | None = Field(
        None,
        ge=5,
        le=100,
        description="重排首轮召回候选数上限",
    )
    visual_embedding_model_config_id: UUID | None = Field(
        default=None,
        description="CLIP 视觉向量化模型；设为 null 可关闭",
    )

    @model_validator(mode="before")
    @classmethod
    def reject_embedding_changes(cls, data: object) -> object:
        """在解析前拦截携带非空 embedding 模型/维度的更新请求。"""
        if isinstance(data, dict):
            forbidden = {
                k
                for k in (
                    "embedding_model_config_id",
                    "embedding_dimension",
                )
                if k in data and data[k] is not None
            }
            if forbidden:
                raise ValueError("向量化模型创建后不可修改，请新建知识库")
        return data


# 知识库详情输出（含已解析的模型名与向量维度）。
class KnowledgeBaseOut(BaseModel):
    id: UUID = Field(description="知识库 ID")
    tenant_id: UUID = Field(description="租户 ID")
    name: str = Field(description="知识库名称")
    description: str | None = Field(default=None, description="描述")
    is_public: bool = Field(description="是否公开")
    embedding_model_config_id: UUID = Field(description="向量化模型配置 ID")
    embedding_model_name: str | None = Field(default=None, description="向量化模型名称")
    embedding_dimension: int = Field(description="向量维度")
    visual_embedding_model_config_id: UUID | None = Field(default=None, description="CLIP 视觉向量化模型 ID")
    visual_embedding_model_name: str | None = Field(default=None, description="CLIP 视觉向量化模型名称")
    chunk_size: int = Field(description="分片大小（字符数）")
    chunk_overlap: int = Field(description="分片重叠长度（字符数）")
    retrieval_mode: str = Field(description="检索策略")
    hybrid_alpha: float = Field(description="混合检索权重")
    rerank_model_config_id: UUID | None = Field(default=None, description="重排模型配置 ID")
    rerank_model_name: str | None = Field(default=None, description="重排模型名称")
    rerank_candidate_k: int = Field(default=50, description="重排首轮召回候选数上限")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


# 文档输出；``chunk_count`` 仅列表接口填充，其余场景为 null。
class DocumentOut(BaseModel):
    id: UUID = Field(description="文档 ID")
    kb_id: UUID = Field(description="所属知识库 ID")
    tenant_id: UUID = Field(description="租户 ID")
    filename: str = Field(description="文件名")
    mime_type: str = Field(description="MIME 类型")
    file_size: int = Field(description="文件大小（字节）")
    status: DocumentStatus = Field(description="处理状态")
    fail_reason: str | None = Field(default=None, description="失败原因")
    celery_task_id: str | None = Field(default=None, description="异步任务 ID")
    chunk_count: int | None = Field(
        None,
        description="已入库分片数（仅列表接口填充；非 ready 或未统计时为 null）",
    )
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


# 文档分片输出。
class DocumentChunkOut(BaseModel):
    id: UUID = Field(description="分片 ID")
    document_id: UUID = Field(description="所属文档 ID")
    kb_id: UUID = Field(description="所属知识库 ID")
    chunk_index: int = Field(description="分片序号")
    content: str = Field(description="分片正文")
    page_no: int | None = Field(default=None, description="页码（如有）")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


class SearchRequest(BaseModel):
    """工作台 KB 检索入参；``mode=default`` 沿用 KB 的 retrieval_mode。"""

    query: str = Field(default="", description="检索查询文本（可与 query_document_id 组合）")
    query_document_id: UUID | None = Field(
        default=None,
        description="以图/视频搜：对该文档 OCR/转写后作为查询（文本搜图/以图搜图 MVP）；visual_search 时为参考图",
    )
    visual_search: bool = Field(
        default=False,
        description="CLIP 视觉相似度检索（需 KB 配置 visual_embedding_model_config_id）",
    )
    media_types: list[MediaType] | None = Field(
        default=None,
        description="限定命中分片的 vector_type；空=全部类型",
    )
    top_k: int = Field(10, ge=1, le=50, description="返回命中条数上限")
    mode: SearchMode = Field(
        "default",
        description="default=使用知识库 retrieval_mode；可单次覆盖为 vector/hybrid",
    )

    @model_validator(mode="after")
    def require_query_or_document(self) -> SearchRequest:
        """要求 ``query`` 与 ``query_document_id`` 至少提供一个。"""
        if not (self.query or "").strip() and not self.query_document_id:
            raise ValueError("query 与 query_document_id 至少提供一项")
        return self


# 单条检索命中（多路分数 + 来源元信息）。
class SearchHit(BaseModel):
    chunk_id: UUID = Field(description="分片 ID")
    document_id: UUID = Field(description="来源文档 ID")
    content: str = Field(description="命中分片正文")
    score: float = Field(description="综合相关度分数")
    score_vector: float | None = Field(default=None, description="向量检索分数")
    score_keyword: float | None = Field(default=None, description="关键词检索分数")
    score_rerank: float | None = Field(default=None, description="重排分数")
    filename: str | None = Field(default=None, description="来源文件名")
    vector_type: str | None = Field(default=None, description="分片媒体类型 text/image/audio/video")
    mime_type: str | None = Field(default=None, description="来源文档 MIME")


# 检索响应：实际使用的检索模式与命中列表。
class SearchResponse(BaseModel):
    query: str = Field(description="检索查询文本")
    mode: str = Field(description="实际使用的检索模式")
    hits: list[SearchHit] = Field(default_factory=list, description="命中结果列表")


# 知识库配额用量与上限。
class KbQuotaOut(BaseModel):
    used_knowledge_bases: int = Field(description="已用知识库数量")
    max_knowledge_bases: int = Field(description="知识库数量上限")
    used_storage_mb: int = Field(description="已用存储（MB）")
    max_storage_mb: int = Field(description="存储上限（MB）")
    max_file_mb: int = Field(description="单文件大小上限（MB）")


# 检索日志输出。
class KbSearchLogOut(BaseModel):
    id: UUID = Field(description="日志 ID")
    tenant_id: UUID = Field(description="租户 ID")
    kb_id: UUID | None = Field(default=None, description="知识库 ID（单库检索）")
    kb_ids: list[str] | None = Field(default=None, description="知识库 ID 列表（多库检索）")
    query: str = Field(description="检索查询文本")
    top_k: int = Field(description="请求返回条数")
    hit_count: int = Field(description="实际命中条数")
    latency_ms: int = Field(description="检索耗时（毫秒）")
    retrieval_mode: str = Field(description="检索模式")
    source: str = Field(description="调用来源")
    actor_user_id: UUID | None = Field(default=None, description="操作用户 ID")
    agent_id: UUID | None = Field(default=None, description="关联智能体 ID")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}
