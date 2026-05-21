from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.app_tenant.marketplace.models import MarketplaceAppStatus


class AppCategoryOut(BaseModel):
    id: UUID
    name: str
    slug: str
    sort_order: int

    model_config = {"from_attributes": True}


class MarketplaceAppOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    icon: str | None
    version: str
    status: MarketplaceAppStatus
    is_official: bool
    install_count: int
    rating_avg: float = 0.0
    rating_count: int = 0
    category_id: UUID | None
    category_name: str | None = None
    installed: bool = False
    review_note: str | None = None
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MarketplaceAppDetail(MarketplaceAppOut):
    manifest: dict
    my_rating: "AppRatingOut | None" = None


class AppReviewBody(BaseModel):
    note: str | None = Field(None, max_length=2000)


class AppRatingCreate(BaseModel):
    score: int = Field(..., ge=1, le=5)
    comment: str | None = Field(None, max_length=2000)


class AppRatingOut(BaseModel):
    id: UUID
    app_id: UUID
    user_id: UUID
    score: int
    comment: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


MarketplaceAppDetail.model_rebuild()


class MarketplaceAppCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    icon: str | None = "📦"
    version: str = "1.0.0"
    category_slug: str | None = None
    manifest: dict = Field(default_factory=dict)
    status: MarketplaceAppStatus = MarketplaceAppStatus.DRAFT


class MarketplaceAppUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = None
    icon: str | None = None
    version: str | None = None
    category_slug: str | None = None
    manifest: dict | None = None
    status: MarketplaceAppStatus | None = None


class MarketplaceAppCreateFromResources(BaseModel):
    """从当前租户已有资源打包上架（草稿）。"""

    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    icon: str | None = "📦"
    category_slug: str | None = "rag"
    flow_id: UUID | None = None
    agent_id: UUID | None = None
    kb_id: UUID | None = None


class AppInstallOut(BaseModel):
    id: UUID
    app_id: UUID
    app_name: str
    tenant_id: UUID
    flow_id: UUID | None
    agent_id: UUID | None
    kb_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AppInstallResult(BaseModel):
    install: AppInstallOut
    flow_id: UUID | None = None
    agent_id: UUID | None = None
    kb_id: UUID | None = None
    message: str = "安装成功"
