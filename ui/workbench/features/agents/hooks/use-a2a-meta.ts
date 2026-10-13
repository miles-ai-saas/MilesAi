"use client";

/**
 * `GET /a2a/peers/meta` — 枚举字典（tenant/a2a/meta.py → api → a2a-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { api } from "@/lib/api";
import { useEnumMeta } from "@/hooks/use-enum-meta";
import type { A2aMeta } from "@/lib/types";

export function useA2aMeta(enabled = true) {
  return useEnumMeta<A2aMeta>("a2a", api.getA2aMeta, enabled);
}
