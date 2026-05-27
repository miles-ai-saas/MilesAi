"""应用市场枚举展示元数据（GET /marketplace/meta）。

- app_statuses / catalog_sorts
- 前端：lib/marketplace-labels.ts、hooks/use-marketplace-meta.ts
- 约定：docs/guides/hooks.md §9
"""

from app.common.schemas.enum_meta import META_SCHEMA_VERSION, enum_options, literal_options
from app.tenant.marketplace.models import MarketplaceAppStatus, MarketplaceAppVisibility

APP_STATUS_LABELS: dict[str, tuple[str, str | None]] = {
    MarketplaceAppStatus.DRAFT.value: ("草稿", "未提交审核"),
    MarketplaceAppStatus.PENDING_REVIEW.value: ("待审核", "已提交，等待平台审核"),
    MarketplaceAppStatus.PUBLISHED.value: ("已上架", "广场可见，可被安装"),
    MarketplaceAppStatus.REJECTED.value: ("已驳回", "可修改后重新提交"),
    MarketplaceAppStatus.ARCHIVED.value: ("已下架", "不再展示与安装"),
}

CATALOG_SORT_OPTIONS: list[tuple[str, str, str | None]] = [
    ("installs", "按安装量", "安装次数降序"),
    ("rating", "按评分", "平均评分降序"),
]

VISIBILITY_LABELS: dict[str, tuple[str, str | None]] = {
    MarketplaceAppVisibility.PUBLIC.value: ("全平台公开", "审核通过后所有租户可见"),
    MarketplaceAppVisibility.TENANT_ONLY.value: ("租户内可见", "仅本租户成员可在广场浏览与安装"),
}


def marketplace_meta_dict() -> dict:
    """构建 meta 响应 dict，供 *MetaOut.model_validate 与单测使用。"""
    return {
        "app_statuses": enum_options(MarketplaceAppStatus, APP_STATUS_LABELS),
        "catalog_sorts": literal_options(CATALOG_SORT_OPTIONS),
        "visibilities": enum_options(MarketplaceAppVisibility, VISIBILITY_LABELS),
        "schema_version": META_SCHEMA_VERSION,
    }
