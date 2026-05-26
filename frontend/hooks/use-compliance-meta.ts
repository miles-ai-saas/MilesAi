"use client";

/**
 * 拉取 GET /compliance/meta 枚举元数据；enabled=false 时不请求。
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
