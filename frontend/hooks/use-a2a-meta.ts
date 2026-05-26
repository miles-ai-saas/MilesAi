"use client";

/**
 * 拉取 GET /a2a/peers/meta 枚举元数据；enabled=false 时不请求（弹窗未打开等）。
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
