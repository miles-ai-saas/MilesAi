"use client";

/**
 * 拉取 GET /monitor/meta 枚举元数据；enabled=false 时不请求（弹窗未打开等）。
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
