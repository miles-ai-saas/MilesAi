"use client";

/**
 * `GET /hooks/meta` — 枚举字典（tenant/hooks/meta.py → api → hooks 页内联 optionLabel，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { HookMeta } from "@/lib/types";

export function useHookMeta(enabled = true) {
  const [meta, setMeta] = useState<HookMeta | null>(null);

  useEffect(() => {
    if (!enabled) return;
    void api.getHookMeta().then(setMeta).catch(() => setMeta(null));
  }, [enabled]);

  return meta;
}
