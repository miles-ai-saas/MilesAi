"use client";

/**
 * 拉取 GET /categories/meta 枚举元数据；enabled=false 时不请求（弹窗未打开等）。
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
