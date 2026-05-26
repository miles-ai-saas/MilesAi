"use client";

/**
 * 拉取 GET /mcp/meta 枚举元数据；enabled=false 时不请求（弹窗未打开等）。
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
