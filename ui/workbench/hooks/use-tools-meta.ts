"use client";

/**
 * `GET /tools/meta` — 枚举字典（tenant/tools/meta.py → api → tool-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { api } from "@/lib/api";
import { useEnumMeta } from "@/hooks/use-enum-meta";
import type { ToolsMeta } from "@/lib/types";

export function useToolsMeta(enabled = true) {
  return useEnumMeta<ToolsMeta>(api.getToolsMeta, enabled);
}
