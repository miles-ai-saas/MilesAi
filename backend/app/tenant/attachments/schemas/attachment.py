from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AttachmentUploadMeta(BaseModel):
    purpose: str = Field(
        default="general",
        max_length=64,
        description="附件用途",
    )
    resource_type: str | None = Field(
        default=None,
        max_length=64,
        description="关联资源类型",
    )
    resource_id: UUID | None = Field(default=None, description="关联资源 ID")


class AttachmentOut(BaseModel):
    id: UUID = Field(description="附件 ID")
    tenant_id: UUID = Field(description="租户 ID")
    uploaded_by: UUID = Field(description="上传用户 ID")
    filename: str = Field(description="原始文件名")
    mime_type: str = Field(description="MIME 类型")
    file_size: int = Field(description="文件大小（字节）")
    object_bucket: str = Field(description="对象存储桶名")
    purpose: str = Field(description="附件用途")
    resource_type: str | None = Field(default=None, description="关联资源类型")
    resource_id: UUID | None = Field(default=None, description="关联资源 ID")
    created_at: datetime = Field(description="上传时间")

    model_config = {"from_attributes": True}
