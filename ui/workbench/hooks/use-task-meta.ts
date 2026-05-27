"use client";

/**
 * `GET /tasks/meta` — 枚举字典（tenant/tasks/meta.py → api → task-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { TaskMeta } from "@/lib/types";

export function useTaskMeta(enabled = true) {
  const [meta, setMeta] = useState<TaskMeta | null>(null);

  useEffect(() => {
    if (!enabled) return;
    void api.getTaskMeta().then(setMeta).catch(() => setMeta(null));
  }, [enabled]);

  return meta;
}
