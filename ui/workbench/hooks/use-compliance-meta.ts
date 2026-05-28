"use client";

/**
 * `GET /compliance/meta` — 枚举字典（tenant/compliance/meta.py → api → compliance-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { api } from "@/lib/api";
import { useEnumMeta } from "@/hooks/use-enum-meta";
import type { ComplianceMeta } from "@/lib/types";

export function useComplianceMeta(enabled = true) {
  return useEnumMeta<ComplianceMeta>(api.getComplianceMeta, enabled);
}
