"use client";

/**
 * `GET /tags/meta` — 枚举字典（tenant/tags/meta.py → api → tag-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { TagMeta } from "@/lib/types";

export function useTagMeta(enabled = true) {
  const [meta, setMeta] = useState<TagMeta | null>(null);

  useEffect(() => {
    if (!enabled) return;
    void api.getTagMeta().then(setMeta).catch(() => setMeta(null));
  }, [enabled]);

  return meta;
}
