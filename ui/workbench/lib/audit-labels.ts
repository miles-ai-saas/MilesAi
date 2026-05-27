/**
 * 审计展示文案：优先 GET /audit/meta，未加载时用本地 fallback。
 * 页面用 optionLabel(meta?.xxx, value)；约定见 docs/guides/hooks.md §9。；链路 §4 见 lib/chains.ts。
 */

import { optionLabel, type EnumOption } from "@/lib/enum-meta";
import type { AuditMeta } from "@/lib/types";

export function auditActionLabel(action: string, meta?: AuditMeta | null): string {
  return optionLabel(meta?.action_labels, action) || action;
}

export function auditResourceTypeLabel(resourceType: string, meta?: AuditMeta | null): string {
  return optionLabel(meta?.resource_types, resourceType) || resourceType;
}

export function auditActionFilterOptions(meta?: AuditMeta | null): EnumOption[] {
  return meta?.action_filters?.length
    ? meta.action_filters
    : [{ value: "", label: "全部动作" }];
}

export function auditResourceTypeFilterOptions(meta?: AuditMeta | null): EnumOption[] {
  return meta?.resource_type_filters?.length
    ? meta.resource_type_filters
    : [{ value: "", label: "全部资源" }];
}
