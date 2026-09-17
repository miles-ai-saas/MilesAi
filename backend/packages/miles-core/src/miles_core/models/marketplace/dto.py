r"""应用市场 API DTO 的兼容壳（真实定义已下沉 ``miles_common.schemas.marketplace``）。

保留本路径与 ``__all__`` 以维持既有 import 稳定（admin services 1 处仍走本路径）。
新代码请直接 import ``miles_common.schemas.marketplace``。

**已知且经查证无消费者的表面变化**：原模块经 `from .models import ...` 顺带导出了
``MarketplaceAppStatus`` / ``MarketplaceAppVisibility``，本壳不再导出这两个 ORM 枚举
（它们已改为在 ``miles_common.schemas.marketplace`` 独立声明）。消费者为零已核实：
``rg -n 'marketplace\.dto import .*(Status|Visibility)'`` 无输出。DTO 定义模块不得反向
依赖 ORM 包。
"""

from miles_common.schemas.marketplace import (
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
