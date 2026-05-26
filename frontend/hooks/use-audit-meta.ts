"use client";

/**
 * 拉取 GET /audit/meta 枚举元数据；enabled=false 时不请求（弹窗未打开等）。
 */


import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AuditMeta } from "@/lib/types";

export function useAuditMeta(enabled = true) {
  const [meta, setMeta] = useState<AuditMeta | null>(null);

  useEffect(() => {
    if (!enabled) return;
    void api.getAuditMeta().then(setMeta).catch(() => setMeta(null));
  }, [enabled]);

  return meta;
}
