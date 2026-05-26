"use client";

/**
 * `GET /tools/meta` — 枚举字典（tenant/tools/meta.py → api → tool-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ToolsMeta } from "@/lib/types";

export function useToolsMeta(enabled = true) {
  const [meta, setMeta] = useState<ToolsMeta | null>(null);

  useEffect(() => {
    if (!enabled) return;
    void api.getToolsMeta().then(setMeta).catch(() => setMeta(null));
  }, [enabled]);

  return meta;
}
