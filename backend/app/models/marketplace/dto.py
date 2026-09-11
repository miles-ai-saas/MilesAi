"""应用市场 API DTO（admin 审核面与 tenant 市场面共用的中立模型）。

实现原居 ``tenant.marketplace.schemas.marketplace``，因 admin 审核需复用同一组 DTO
（且不得反向依赖租户域）而整体下沉；``tenant.marketplace.schemas.marketplace`` 转
re-export 保持既有 import 稳定。依赖仅 pydantic/uuid/datetime + 中立模型，不含业务逻辑。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.common.schemas.tag import TagRefOut
from app.models.marketplace.models import MarketplaceAppStatus, MarketplaceAppVisibility


# 应用分类出参。
class AppCategoryOut(BaseModel):
    id: UUID = Field(description="分类 ID")
    name: str = Field(description="分类名称")
    slug: str = Field(description="分类 slug")
    sort_order: int = Field(description="排序权重")

    model_config = {"from_attributes": True}


# 市场应用列表出参（含当前租户安装态与评分）。
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


# 应用详情出参：列表字段 + manifest 与当前用户评分。
class MarketplaceAppDetail(MarketplaceAppOut):
    manifest: dict = Field(description="应用清单（资源引用与配置）")
    my_rating: "AppRatingOut | None" = Field(default=None, description="当前用户的评分记录")


# 审核请求体（审核意见）。
class AppReviewBody(BaseModel):
    note: str | None = Field(
        default=None,
        max_length=2000,
        description="审核意见",
    )


# 提交应用评分入参。
class AppRatingCreate(BaseModel):
    score: int = Field(..., ge=1, le=5, description="评分（1–5）")
    comment: str | None = Field(
        default=None,
        max_length=2000,
        description="评价内容",
    )


# 应用评分记录出参。
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


# 创建应用（草稿）入参。
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


# 更新应用入参；字段均可选，None 表示不修改。
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


# 应用安装记录出参。
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


# 安装结果：安装记录 + 新克隆的资源 ID。
class AppInstallResult(BaseModel):
    install: AppInstallOut = Field(description="安装记录")
    flow_id: UUID | None = Field(default=None, description="新创建的流程 ID")
    agent_id: UUID | None = Field(default=None, description="新创建的智能体 ID")
    kb_id: UUID | None = Field(default=None, description="新创建的知识库 ID")
    message: str = Field(default="安装成功", description="结果说明")


# 升级结果：安装记录 + 版本变化。
class AppUpgradeResult(BaseModel):
    install: AppInstallOut = Field(description="安装记录")
    previous_version: str = Field(description="升级前版本")
    new_version: str = Field(description="升级后版本")
    message: str = Field(default="升级成功", description="结果说明")


# 单个字段的升级前后对比。
class UpgradeFieldChange(BaseModel):
    field: str = Field(description="字段键")
    label: str = Field(description="展示标签")
    before: str | None = Field(default=None, description="当前值")
    after: str | None = Field(default=None, description="升级后值")
    changed: bool = Field(description="是否有差异")


# 单资源（KB/Flow/Agent）的字段差异集合。
class UpgradeResourceDiff(BaseModel):
    resource_type: str = Field(description="knowledge_base | flow | agent")
    resource_id: UUID | None = Field(default=None, description="租户内资源 ID")
    resource_name: str = Field(description="资源名称")
    changes: list[UpgradeFieldChange] = Field(default_factory=list, description="字段对比")
    has_changes: bool = Field(default=False, description="该资源是否存在差异")


# 升级预览：目标版本与资源 diff，供前端确认。
class AppUpgradePreview(BaseModel):
    app_id: UUID = Field(description="应用 ID")
    app_name: str = Field(description="应用名称")
    installed_version: str = Field(description="已安装版本")
    target_version: str = Field(description="市场目标版本")
    can_upgrade: bool = Field(description="是否可升级（版本不同）")
    has_changes: bool = Field(description="manifest 与当前资源是否存在字段差异")
    message: str | None = Field(default=None, description="提示说明")
    resources: list[UpgradeResourceDiff] = Field(default_factory=list, description="资源 diff")


# 回滚预览：目标版本与资源 diff。
class AppRollbackPreview(BaseModel):
    app_id: UUID = Field(description="应用 ID")
    app_name: str = Field(description="应用名称")
    current_version: str = Field(description="当前已安装版本")
    target_version: str = Field(description="回滚目标版本")
    can_rollback: bool = Field(description="是否可执行回滚")
    resources: list[UpgradeResourceDiff] = Field(default_factory=list, description="资源 diff")
    message: str = Field(default="", description="说明")


# 回滚结果：安装记录 + 版本变化。
class AppRollbackResult(BaseModel):
    install: AppInstallOut = Field(description="安装记录")
    previous_version: str = Field(description="回滚前版本")
    restored_version: str = Field(description="恢复后的版本")
    message: str = Field(default="回滚成功", description="结果说明")
