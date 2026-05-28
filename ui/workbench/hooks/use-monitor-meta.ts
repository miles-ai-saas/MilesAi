"use client";

/**
 * `GET /monitor/meta` — 枚举字典（tenant/monitor/meta.py → api → monitor-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { api } from "@/lib/api";
import { useEnumMeta } from "@/hooks/use-enum-meta";
import type { MonitorMeta } from "@/lib/types";

export function useMonitorMeta(enabled = true) {
  return useEnumMeta<MonitorMeta>(api.getMonitorMeta, enabled);
}
