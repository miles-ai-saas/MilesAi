"use client";

/**
 * 拉取 GET /agents/meta 枚举元数据；enabled=false 时不请求（弹窗未打开等）。
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
