"use client";

/**
 * `GET /tasks/meta` — 枚举字典（tenant/tasks/meta.py → api → task-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { api } from "@/lib/api";
import { useEnumMeta } from "@/hooks/use-enum-meta";
import type { TaskMeta } from "@/lib/types";

export function useTaskMeta(enabled = true) {
  return useEnumMeta<TaskMeta>("tasks", api.getTaskMeta, enabled);
}
