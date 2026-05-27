from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.tenant.marketplace.models import MarketplaceAppStatus, MarketplaceAppVisibility
from app.tenant.tags.schemas.tag import TagRefOut


class AppCategoryOut(BaseModel):
    id: UUID = Field(description="分类 ID")
    name: str = Field(description="分类名称")
    slug: str = Field(description="分类 slug")
    sort_order: int = Field(description="排序权重")

    model_config = {"from_attributes": True}


class MarketplaceAppOut(BaseModel):
    id: UUID = Field(description="应用 ID")
    name: str = Field(description="应用名称")
    description: str | None = Field(default=None, description="应用描述")
    icon: str | None = Field(default=None, description="图标（emoji 或 URL）")
    version: str = Field(description="版本号")
    status: MarketplaceAppStatus = Field(description="上架状态")
    is_official: bool = Field(description="是否官方应用")
    install_count: int = Field(description="安装次数")
    rating_avg: float = Field(default=0.0, description="平均评分")
    rating_count: int = Field(default=0, description="评分人数")
    visibility: str = Field(default="public", description="可见范围：public | tenant_only")
    category_id: UUID | None = Field(default=None, description="分类 ID")
    category_name: str | None = Field(default=None, description="分类名称")
    tags: list[TagRefOut] = Field(default_factory=list, description="标签列表")
    installed: bool = Field(default=False, description="当前租户是否已安装")
    review_note: str | None = Field(default=None, description="审核备注")
    submitted_at: datetime | None = Field(default=None, description="提交审核时间")
    reviewed_at: datetime | None = Field(default=None, description="审核完成时间")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


class MarketplaceAppDetail(MarketplaceAppOut):
    manifest: dict = Field(description="应用清单（资源引用与配置）")
    my_rating: "AppRatingOut | None" = Field(default=None, description="当前用户的评分记录")


class AppReviewBody(BaseModel):
    note: str | None = Field(
        default=None,
        max_length=2000,
        description="审核意见",
    )


class AppRatingCreate(BaseModel):
    score: int = Field(..., ge=1, le=5, description="评分（1–5）")
    comment: str | None = Field(
        default=None,
        max_length=2000,
        description="评价内容",
    )


class AppRatingOut(BaseModel):
    id: UUID = Field(description="评分记录 ID")
    app_id: UUID = Field(description="应用 ID")
    user_id: UUID = Field(description="用户 ID")
    score: int = Field(description="评分（1–5）")
    comment: str | None = Field(default=None, description="评价内容")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    model_config = {"from_attributes": True}


MarketplaceAppDetail.model_rebuild()


class MarketplaceAppCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="应用名称")
    description: str | None = Field(default=None, description="应用描述")
    icon: str | None = Field(default="📦", description="图标")
    version: str = Field(default="1.0.0", description="版本号")
    category_slug: str | None = Field(default=None, description="分类 slug")
    manifest: dict = Field(default_factory=dict, description="应用清单 JSON")
    status: MarketplaceAppStatus = Field(
        default=MarketplaceAppStatus.DRAFT,
        description="上架状态",
    )
    tag_ids: list[UUID] = Field(default_factory=list, description="标签 ID 列表")
    visibility: MarketplaceAppVisibility = Field(
        default=MarketplaceAppVisibility.PUBLIC,
        description="可见范围",
    )


class MarketplaceAppUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="应用名称",
    )
    description: str | None = Field(default=None, description="应用描述")
    icon: str | None = Field(default=None, description="图标")
    version: str | None = Field(default=None, description="版本号")
    category_slug: str | None = Field(default=None, description="分类 slug")
    manifest: dict | None = Field(default=None, description="应用清单 JSON")
    status: MarketplaceAppStatus | None = Field(default=None, description="上架状态")
    tag_ids: list[UUID] | None = Field(default=None, description="标签 ID 列表（全量替换）")
    visibility: MarketplaceAppVisibility | None = Field(default=None, description="可见范围")


class MarketplaceAppCreateFromResources(BaseModel):
    """从当前租户已有资源打包上架（草稿）。"""

    name: str = Field(..., min_length=1, max_length=128, description="应用名称")
    description: str | None = Field(default=None, description="应用描述")
    icon: str | None = Field(default="📦", description="图标")
    category_slug: str | None = Field(default="rag", description="分类 slug")
    flow_id: UUID | None = Field(default=None, description="打包的流程 ID")
    agent_id: UUID | None = Field(default=None, description="打包的智能体 ID")
    kb_id: UUID | None = Field(default=None, description="打包的知识库 ID")
    tag_ids: list[UUID] = Field(default_factory=list, description="标签 ID 列表")
    visibility: MarketplaceAppVisibility = Field(
        default=MarketplaceAppVisibility.PUBLIC,
        description="可见范围",
    )


class AppInstallOut(BaseModel):
    id: UUID = Field(description="安装记录 ID")
    app_id: UUID = Field(description="应用 ID")
    app_name: str = Field(description="应用名称")
    tenant_id: UUID = Field(description="租户 ID")
    installed_version: str = Field(default="1.0.0", description="已安装版本")
    app_version: str | None = Field(default=None, description="市场当前版本")
    flow_id: UUID | None = Field(default=None, description="安装后创建的流程 ID")
    agent_id: UUID | None = Field(default=None, description="安装后创建的智能体 ID")
    kb_id: UUID | None = Field(default=None, description="安装后创建的知识库 ID")
    created_at: datetime = Field(description="安装时间")

    model_config = {"from_attributes": True}


class AppInstallResult(BaseModel):
    install: AppInstallOut = Field(description="安装记录")
    flow_id: UUID | None = Field(default=None, description="新创建的流程 ID")
    agent_id: UUID | None = Field(default=None, description="新创建的智能体 ID")
    kb_id: UUID | None = Field(default=None, description="新创建的知识库 ID")
    message: str = Field(default="安装成功", description="结果说明")


class AppUpgradeResult(BaseModel):
    install: AppInstallOut = Field(description="安装记录")
    previous_version: str = Field(description="升级前版本")
    new_version: str = Field(description="升级后版本")
    message: str = Field(default="升级成功", description="结果说明")
