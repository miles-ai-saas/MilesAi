"use client";

/**
 * `GET /tags/meta` — 枚举字典（tenant/tags/meta.py → api → tag-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { api } from "@/lib/api";
import { useEnumMeta } from "@/hooks/use-enum-meta";
import type { TagMeta } from "@/lib/types";

export function useTagMeta(enabled = true) {
  return useEnumMeta<TagMeta>("tags", api.getTagMeta, enabled);
}
