"use client";

/**
 * `GET /categories/meta` — 枚举字典（tenant/categories/meta.py → api → category-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CategoryMeta } from "@/lib/types";

export function useCategoryMeta(enabled = true) {
  const [meta, setMeta] = useState<CategoryMeta | null>(null);

  useEffect(() => {
    if (!enabled) return;
    void api.getCategoryMeta().then(setMeta).catch(() => setMeta(null));
  }, [enabled]);

  return meta;
}
