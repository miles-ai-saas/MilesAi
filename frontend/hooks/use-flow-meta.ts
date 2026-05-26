"use client";

/**
 * `GET /flows/meta` — 枚举字典（tenant/flows/meta.py → api → flow-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { FlowMeta } from "@/lib/types";

export function useFlowMeta(enabled = true) {
  const [meta, setMeta] = useState<FlowMeta | null>(null);

  useEffect(() => {
    if (!enabled) return;
    void api.getFlowMeta().then(setMeta).catch(() => setMeta(null));
  }, [enabled]);

  return meta;
}
