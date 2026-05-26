"use client";

/**
 * `GET /a2a/peers/meta` — 枚举字典（tenant/a2a/meta.py → api → a2a-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { A2aMeta } from "@/lib/types";

export function useA2aMeta(enabled = true) {
  const [meta, setMeta] = useState<A2aMeta | null>(null);

  useEffect(() => {
    if (!enabled) return;
    void api.getA2aMeta().then(setMeta).catch(() => setMeta(null));
  }, [enabled]);

  return meta;
}
