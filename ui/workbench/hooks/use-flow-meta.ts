"use client";

/**
 * `GET /flows/meta` — 枚举字典（tenant/flows/meta.py → api → flow-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { api } from "@/lib/api";
import { useEnumMeta } from "@/hooks/use-enum-meta";
import type { FlowMeta } from "@/lib/types";

export function useFlowMeta(enabled = true) {
  return useEnumMeta<FlowMeta>("flows", api.getFlowMeta, enabled);
}
