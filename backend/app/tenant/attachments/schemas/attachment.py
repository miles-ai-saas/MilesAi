from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AttachmentUploadMeta(BaseModel):
    purpose: str = Field("general", max_length=64)
    resource_type: str | None = Field(None, max_length=64)
    resource_id: UUID | None = None


class AttachmentOut(BaseModel):
    id: UUID
    tenant_id: UUID
    uploaded_by: UUID
    filename: str
    mime_type: str
    file_size: int
    object_bucket: str
    purpose: str
    resource_type: str | None
    resource_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}
