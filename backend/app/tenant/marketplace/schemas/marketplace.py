"""市场 API DTO 的 L1 兼容入口。

实现已上移中立域 ``app.models.marketplace.dto``（admin 审核面与 tenant 市场面共用）；
本模块仅 re-export，保持既有 ``app.tenant.marketplace.schemas.marketplace`` import 稳定。
"""

from __future__ import annotations

from app.models.marketplace.dto import (
    AppCategoryOut,
    AppInstallOut,
    AppInstallResult,
    AppRatingCreate,
    AppRatingOut,
    AppReviewBody,
    AppRollbackPreview,
    AppRollbackResult,
    AppUpgradePreview,
    AppUpgradeResult,
    MarketplaceAppCreate,
    MarketplaceAppCreateFromResources,
    MarketplaceAppDetail,
    MarketplaceAppOut,
    MarketplaceAppUpdate,
    UpgradeFieldChange,
    UpgradeResourceDiff,
)

__all__ = [
    "AppCategoryOut",
    "AppInstallOut",
    "AppInstallResult",
    "AppRatingCreate",
    "AppRatingOut",
    "AppReviewBody",
    "AppRollbackPreview",
    "AppRollbackResult",
    "AppUpgradePreview",
    "AppUpgradeResult",
    "MarketplaceAppCreate",
    "MarketplaceAppCreateFromResources",
    "MarketplaceAppDetail",
    "MarketplaceAppOut",
    "MarketplaceAppUpdate",
    "UpgradeFieldChange",
    "UpgradeResourceDiff",
]
