"use client";

/**
 * `GET /agents/meta` — 枚举字典（tenant/agents/meta.py → api → agent-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { api } from "@/lib/api";
import { useEnumMeta } from "@/hooks/use-enum-meta";
import type { AgentMeta } from "@/lib/types";

export function useAgentMeta(enabled = true) {
  return useEnumMeta<AgentMeta>("agents", api.getAgentMeta, enabled);
}
