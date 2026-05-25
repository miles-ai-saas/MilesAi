from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.kb import DocumentStatus

RetrievalMode = Literal["vector", "hybrid"]
SearchMode = Literal["default", "vector", "hybrid"]


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    is_public: bool = False
    chunk_size: int = Field(500, ge=100, le=4000)
    chunk_overlap: int = Field(50, ge=0, le=500)
    embedding_model_config_id: UUID | None = Field(
        None,
        description="向量化模型（model_type=embedding），默认内置 BGE；创建后不可修改",
    )
    retrieval_mode: RetrievalMode = Field(
        "vector",
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


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_public: bool | None = None
    chunk_size: int | None = Field(None, ge=100, le=4000)
    chunk_overlap: int | None = Field(None, ge=0, le=500)
    retrieval_mode: RetrievalMode | None = None
    hybrid_alpha: float | None = Field(None, ge=0.0, le=1.0)
    rerank_model_config_id: UUID | None = None
    rerank_candidate_k: int | None = Field(None, ge=5, le=100)

    @model_validator(mode="before")
    @classmethod
    def reject_embedding_changes(cls, data: object) -> object:
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


class KnowledgeBaseOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    is_public: bool
    embedding_model_config_id: UUID
    embedding_model_name: str | None = None
    embedding_dimension: int
    chunk_size: int
    chunk_overlap: int
    retrieval_mode: str
    hybrid_alpha: float
    rerank_model_config_id: UUID | None = None
    rerank_model_name: str | None = None
    rerank_candidate_k: int = 50
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentOut(BaseModel):
    id: UUID
    kb_id: UUID
    tenant_id: UUID
    filename: str
    mime_type: str
    file_size: int
    status: DocumentStatus
    fail_reason: str | None
    celery_task_id: str | None
    chunk_count: int | None = Field(
        None,
        description="已入库分片数（仅列表接口填充；非 ready 或未统计时为 null）",
    )
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentChunkOut(BaseModel):
    id: UUID
    document_id: UUID
    kb_id: UUID
    chunk_index: int
    content: str
    page_no: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(10, ge=1, le=50)
    mode: SearchMode = Field(
        "default",
        description="default=使用知识库 retrieval_mode；可单次覆盖为 vector/hybrid",
    )


class SearchHit(BaseModel):
    chunk_id: UUID
    document_id: UUID
    content: str
    score: float
    score_vector: float | None = None
    score_keyword: float | None = None
    score_rerank: float | None = None
    filename: str | None = None


class SearchResponse(BaseModel):
    query: str
    mode: str
    hits: list[SearchHit]


class KbQuotaOut(BaseModel):
    used_knowledge_bases: int
    max_knowledge_bases: int
    used_storage_mb: int
    max_storage_mb: int
    max_file_mb: int


class KbSearchLogOut(BaseModel):
    id: UUID
    tenant_id: UUID
    kb_id: UUID | None
    kb_ids: list[str] | None
    query: str
    top_k: int
    hit_count: int
    latency_ms: int
    retrieval_mode: str
    source: str
    actor_user_id: UUID | None
    agent_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}
