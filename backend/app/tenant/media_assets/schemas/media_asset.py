from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.tenant.attachments.schemas.attachment import AttachmentOut


class MediaAssetOut(BaseModel):
    id: UUID = Field(description="媒体资产 ID")
    tenant_id: UUID = Field(description="租户 ID")
    attachment_id: UUID = Field(description="关联附件 ID")
    cover_attachment_id: UUID | None = Field(
        default=None,
        description="视频封面图附件 ID（列表缩略图）",
    )
    kind: str = Field(description="媒体类型（如 image、video）")
    source: str = Field(description="来源标识")
    source_ref_type: str | None = Field(default=None, description="来源资源类型")
    source_ref_id: UUID | None = Field(default=None, description="来源资源 ID")
    prompt: str | None = Field(default=None, description="生成时使用的提示词")
    model_config_id: UUID | None = Field(default=None, description="使用的模型配置 ID")
    title: str | None = Field(default=None, description="标题")
    tags: list[str] | None = Field(default=None, description="标签列表")
    kb_id: UUID | None = Field(default=None, description="已入库的知识库 ID")
    kb_document_id: UUID | None = Field(default=None, description="知识库文档 ID")
    promoted_at: datetime | None = Field(default=None, description="入库时间")
    created_by: UUID = Field(description="创建用户 ID")
    created_at: datetime = Field(description="创建时间")
    attachment: AttachmentOut | None = Field(default=None, description="关联附件详情")
    cover_attachment: AttachmentOut | None = Field(
        default=None,
        description="视频封面附件详情",
    )

    model_config = {"from_attributes": True}


class MediaAssetUpdate(BaseModel):
    title: str | None = Field(
        default=None,
        max_length=512,
        description="标题",
    )
    tags: list[str] | None = Field(default=None, description="标签列表")


class PromoteToKbRequest(BaseModel):
    kb_id: UUID = Field(description="目标知识库 ID")
    filename: str | None = Field(
        default=None,
        max_length=512,
        description="入库后的文档文件名",
    )
    run_parse: bool = Field(default=True, description="入库后是否触发解析")
