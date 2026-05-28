"use client";

/**
 * `GET /categories/meta` — 枚举字典（tenant/categories/meta.py → api → category-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { api } from "@/lib/api";
import { useEnumMeta } from "@/hooks/use-enum-meta";
import type { CategoryMeta } from "@/lib/types";

export function useCategoryMeta(enabled = true) {
  return useEnumMeta<CategoryMeta>(api.getCategoryMeta, enabled);
}
