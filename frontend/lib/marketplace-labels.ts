/**
 * 应用市场展示文案：优先 GET /marketplace/meta，未加载时用本地 fallback。
 * 页面用 optionLabel(meta?.xxx, value)；约定见 docs/guides/hooks.md §9。；链路 §4 见 lib/chains.ts。
 */

import { optionLabel, type EnumOption } from "@/lib/enum-meta";
import type { MarketplaceMeta } from "@/lib/types";

const STATUS_FALLBACK: Record<string, string> = {
  draft: "草稿",
  pending_review: "待审核",
  published: "已上架",
  rejected: "已驳回",
  archived: "已下架",
};

const SORT_FALLBACK: EnumOption[] = [
  { value: "installs", label: "按安装量" },
  { value: "rating", label: "按评分" },
];

export function marketplaceStatusLabel(status: string, meta?: MarketplaceMeta | null): string {
  return optionLabel(meta?.app_statuses, status) || STATUS_FALLBACK[status] || status;
}

export function marketplaceCatalogSortOptions(meta?: MarketplaceMeta | null): EnumOption[] {
  return meta?.catalog_sorts?.length ? meta.catalog_sorts : SORT_FALLBACK;
}
