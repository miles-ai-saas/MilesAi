/**
 * 监控展示文案：优先 GET /monitor/meta，未加载时用本地 fallback。
 * 页面用 optionLabel(meta?.xxx, value)；约定见 docs/guides/hooks.md §9。；链路 §4 见 lib/chains.ts。
 */

import { optionLabel, type EnumOption } from "@/lib/enum-meta";
import type { MonitorMeta } from "@/lib/types";

const COMPONENT_FALLBACK: Record<string, string> = {
  postgres: "PostgreSQL",
  redis: "Redis",
  vector_store: "向量库",
  object_storage: "对象存储",
};

const HEALTH_FALLBACK: Record<string, string> = {
  healthy: "正常",
  degraded: "降级",
  unhealthy: "异常",
};

const TREND_DAYS_FALLBACK: EnumOption[] = [
  { value: "7", label: "近 7 天" },
  { value: "14", label: "近 14 天" },
  { value: "30", label: "近 30 天" },
];

export function monitorHealthComponentLabel(key: string, meta?: MonitorMeta | null): string {
  return optionLabel(meta?.health_components, key) || COMPONENT_FALLBACK[key] || key;
}

export function monitorOverallHealthLabel(
  status: string | undefined,
  ok: boolean,
  meta?: MonitorMeta | null,
): string {
  if (status) {
    return optionLabel(meta?.overall_health_statuses, status) || HEALTH_FALLBACK[status] || status;
  }
  return ok ? HEALTH_FALLBACK.healthy : HEALTH_FALLBACK.unhealthy;
}

export function monitorTrendDayOptions(meta?: MonitorMeta | null): EnumOption[] {
  return meta?.trend_day_ranges?.length ? meta.trend_day_ranges : TREND_DAYS_FALLBACK;
}
