"use client";

/**
 * `GET /compliance/meta` — 枚举字典（tenant/compliance/meta.py → api → compliance-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ComplianceMeta } from "@/lib/types";

export function useComplianceMeta(enabled = true) {
  const [meta, setMeta] = useState<ComplianceMeta | null>(null);

  useEffect(() => {
    if (!enabled) return;
    void api.getComplianceMeta().then(setMeta).catch(() => setMeta(null));
  }, [enabled]);

  return meta;
}
