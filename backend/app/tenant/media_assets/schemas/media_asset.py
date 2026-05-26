from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.tenant.attachments.schemas.attachment import AttachmentOut


class MediaAssetOut(BaseModel):
    id: UUID
    tenant_id: UUID
    attachment_id: UUID
    kind: str
    source: str
    source_ref_type: str | None
    source_ref_id: UUID | None
    prompt: str | None
    model_config_id: UUID | None
    title: str | None
    tags: list[str] | None
    kb_id: UUID | None
    kb_document_id: UUID | None
    promoted_at: datetime | None
    created_by: UUID
    created_at: datetime
    attachment: AttachmentOut | None = None

    model_config = {"from_attributes": True}


class MediaAssetUpdate(BaseModel):
    title: str | None = Field(None, max_length=512)
    tags: list[str] | None = None


class PromoteToKbRequest(BaseModel):
    kb_id: UUID
    filename: str | None = Field(None, max_length=512)
    run_parse: bool = True
