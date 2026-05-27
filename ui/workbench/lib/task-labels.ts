/**
 * 异步任务展示文案：优先 `GET /tasks/meta`（`useTaskMeta`），未加载时本地 fallback。
 * 链路见 `lib/enum-meta.ts`。；链路 §4 见 lib/chains.ts。
 */

import { optionLabel, type EnumOption } from "@/lib/enum-meta";
import type { TaskMeta } from "@/lib/types";

const STATUS_FALLBACK: Record<string, string> = {
  pending: "等待中",
  running: "运行中",
  success: "成功",
  failed: "失败",
  cancelled: "已取消",
};

const FILTER_FALLBACK: EnumOption[] = [
  { value: "", label: "全部" },
  { value: "pending", label: "等待中" },
  { value: "running", label: "运行中" },
  { value: "failed", label: "失败" },
  { value: "success", label: "成功" },
];

export function taskStatusLabel(status: string, meta?: TaskMeta | null): string {
  return optionLabel(meta?.statuses, status) || STATUS_FALLBACK[status] || status;
}

export function taskStatusFilterOptions(meta?: TaskMeta | null): EnumOption[] {
  return meta?.status_filters?.length ? meta.status_filters : FILTER_FALLBACK;
}

export function taskStatusBadgeClass(status: string): string {
  switch (status) {
    case "success":
      return "bg-emerald-50 text-emerald-800 ring-emerald-200";
    case "failed":
      return "bg-red-50 text-red-700 ring-red-200";
    case "running":
      return "bg-amber-50 text-amber-800 ring-amber-200";
    case "pending":
      return "bg-surface-muted text-ink-muted ring-line";
    case "cancelled":
      return "bg-surface-muted text-ink-faint ring-line";
    default:
      return "bg-surface-muted text-ink-muted ring-line";
  }
}
