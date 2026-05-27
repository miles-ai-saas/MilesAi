"use client";

/**
 * `GET /agents/meta` — 枚举字典（tenant/agents/meta.py → api → agent-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AgentMeta } from "@/lib/types";

export function useAgentMeta(enabled = true) {
  const [meta, setMeta] = useState<AgentMeta | null>(null);

  useEffect(() => {
    if (!enabled) return;
    void api.getAgentMeta().then(setMeta).catch(() => setMeta(null));
  }, [enabled]);

  return meta;
}
