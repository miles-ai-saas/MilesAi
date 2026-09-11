"""应用市场枚举展示元数据（GET /marketplace/meta）。

- app_statuses / catalog_sorts
- 前端：lib/marketplace-labels.ts、hooks/use-marketplace-meta.ts
- 约定：docs/guides/hooks.md §9
"""

from miles_common.schemas.enum_meta import META_SCHEMA_VERSION, enum_options, literal_options
from miles_portal.tenant.marketplace.models import MarketplaceAppStatus, MarketplaceAppVisibility

APP_STATUS_LABELS: dict[str, tuple[str, str | None]] = {
    MarketplaceAppStatus.DRAFT.value: ("草稿", "未提交审核"),
    MarketplaceAppStatus.PENDING_REVIEW.value: ("待审核", "已提交，等待审核"),
    MarketplaceAppStatus.PUBLISHED.value: ("已上架", "广场可见，可被安装"),
    MarketplaceAppStatus.REJECTED.value: ("已驳回", "可修改后重新提交"),
    MarketplaceAppStatus.ARCHIVED.value: ("已下架", "不再展示与安装"),
}

PENDING_REVIEW_PLATFORM_LABEL = ("待平台审核", "已提交，等待平台运营审核")

CATALOG_SORT_OPTIONS: list[tuple[str, str, str | None]] = [
    ("installs", "按安装量", "安装次数降序"),
    ("rating", "按评分", "平均评分降序"),
]

VISIBILITY_LABELS: dict[str, tuple[str, str | None]] = {
    MarketplaceAppVisibility.PUBLIC.value: ("全平台公开", "审核通过后所有租户可见"),
    MarketplaceAppVisibility.TENANT_ONLY.value: ("租户内可见", "仅本租户成员可在广场浏览与安装"),
}


def marketplace_meta_dict(*, review_mode: str = "platform") -> dict:
    """构建 meta 响应 dict，供 *MetaOut.model_validate 与单测使用。"""
    status_labels = dict(APP_STATUS_LABELS)
    if review_mode == "platform":
        status_labels[MarketplaceAppStatus.PENDING_REVIEW.value] = PENDING_REVIEW_PLATFORM_LABEL
    return {
        "app_statuses": enum_options(MarketplaceAppStatus, status_labels),
        "catalog_sorts": literal_options(CATALOG_SORT_OPTIONS),
        "visibilities": enum_options(MarketplaceAppVisibility, VISIBILITY_LABELS),
        "review_mode": review_mode,
        "schema_version": META_SCHEMA_VERSION,
    }
