"use client";

/**
 * `GET /hooks/meta` — 枚举字典（tenant/hooks/meta.py → api → hooks 页内联 optionLabel，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { api } from "@/lib/api";
import { useEnumMeta } from "@/hooks/use-enum-meta";
import type { HookMeta } from "@/lib/types";

export function useHookMeta(enabled = true) {
  return useEnumMeta<HookMeta>(api.getHookMeta, enabled);
}
