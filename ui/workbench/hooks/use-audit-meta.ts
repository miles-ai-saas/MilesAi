"use client";

/**
 * `GET /audit/meta` — 枚举字典（tenant/audit_log/meta.py → api → audit-labels，见 lib/chains.ts §4、`enum-meta.ts`）。
 * `enabled=false` 时不请求。
 */

import { api } from "@/lib/api";
import { useEnumMeta } from "@/hooks/use-enum-meta";
import type { AuditMeta } from "@/lib/types";

export function useAuditMeta(enabled = true) {
  return useEnumMeta<AuditMeta>("audit", api.getAuditMeta, enabled);
}
