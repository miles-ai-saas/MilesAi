"use client";

/**
 * `GET /kb/meta` — 枚举字典（tenant/kb/meta.py → api → kb-labels / document-status，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { api } from "@/lib/api";
import { useEnumMeta } from "@/hooks/use-enum-meta";
import type { KbMeta } from "@/lib/types";

export function useKbMeta(enabled = true) {
  return useEnumMeta<KbMeta>("kb", api.getKbMeta, enabled);
}
