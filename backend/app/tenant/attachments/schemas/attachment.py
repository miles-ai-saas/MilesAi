"""附件上传元数据与输出 schema。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# 上传附件时携带的业务归属信息（用途与关联资源）。
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


# 附件对外输出；不含对象存储 key，读取需走内容接口鉴权。
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
