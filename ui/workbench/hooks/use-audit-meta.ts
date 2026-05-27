"use client";

/**
 * `GET /audit/meta` — 枚举字典（tenant/audit_log/meta.py → api → audit-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
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
