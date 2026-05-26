/**
 * 流程状态展示文案：优先 GET /flows/meta，未加载时用本地 fallback。
 * 页面用 optionLabel(meta?.statuses, value)；约定见 docs/guides/hooks.md §9。
 */

import { optionLabel } from "@/lib/enum-meta";
import type { FlowMeta } from "@/lib/types";

const STATUS_FALLBACK: Record<string, string> = {
  draft: "草稿",
  published: "已发布",
};

export function flowStatusLabel(status: string, meta?: FlowMeta | null): string {
  return optionLabel(meta?.statuses, status) || STATUS_FALLBACK[status] || status;
}
