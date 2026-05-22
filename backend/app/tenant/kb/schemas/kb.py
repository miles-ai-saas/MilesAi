from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.kb import DocumentStatus


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


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_public: bool | None = None
    chunk_size: int | None = Field(None, ge=100, le=4000)
    chunk_overlap: int | None = Field(None, ge=0, le=500)

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
    created_at: datetime

    model_config = {"from_attributes": True}


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(10, ge=1, le=50)


class SearchHit(BaseModel):
    chunk_id: UUID
    document_id: UUID
    content: str
    score: float
    filename: str | None = None


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]
