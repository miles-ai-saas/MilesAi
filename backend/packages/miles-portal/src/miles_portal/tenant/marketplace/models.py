"""应用市场 ORM 的 L1 兼容入口。

实现已上移 ``miles_core.models.marketplace``（admin 与 tenant 共读的共享 ORM）；
本模块仅 re-export，保持既有 ``miles_portal.tenant.marketplace.models`` import 稳定。
"""

from __future__ import annotations

from miles_core.models.marketplace.models import (
    AppCategory,
    AppInstall,
    AppInstallSnapshot,
    AppRating,
    MarketplaceApp,
    MarketplaceAppStatus,
    MarketplaceAppVisibility,
)

__all__ = [
    "AppCategory",
    "AppInstall",
    "AppInstallSnapshot",
    "AppRating",
    "MarketplaceApp",
    "MarketplaceAppStatus",
    "MarketplaceAppVisibility",
]
