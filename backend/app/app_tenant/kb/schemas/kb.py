from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.kb import DocumentStatus


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    is_public: bool = False
    chunk_size: int = Field(500, ge=100, le=4000)
    chunk_overlap: int = Field(50, ge=0, le=500)


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_public: bool | None = None
    chunk_size: int | None = Field(None, ge=100, le=4000)
    chunk_overlap: int | None = Field(None, ge=0, le=500)


class KnowledgeBaseOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    is_public: bool
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
