"use client";

/**
 * `GET /monitor/meta` — 枚举字典（tenant/monitor/meta.py → api → monitor-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { MonitorMeta } from "@/lib/types";

export function useMonitorMeta(enabled = true) {
  const [meta, setMeta] = useState<MonitorMeta | null>(null);

  useEffect(() => {
    if (!enabled) return;
    void api.getMonitorMeta().then(setMeta).catch(() => setMeta(null));
  }, [enabled]);

  return meta;
}
