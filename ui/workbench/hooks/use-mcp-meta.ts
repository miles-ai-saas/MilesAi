"use client";

/**
 * `GET /mcp/meta` — 枚举字典（tenant/mcp/meta.py → api → mcp-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { McpMeta } from "@/lib/types";

export function useMcpMeta(enabled = true) {
  const [meta, setMeta] = useState<McpMeta | null>(null);

  useEffect(() => {
    if (!enabled) return;
    void api.getMcpMeta().then(setMeta).catch(() => setMeta(null));
  }, [enabled]);

  return meta;
}
