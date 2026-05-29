import type { AuditDatePreset } from "@/lib/audit-labels";

export const AUDIT_PAGE_DESCRIPTION = "平台级操作记录，支持按操作人、时间与租户追溯（私有化合规）";

export const AUDIT_DATE_PRESETS: { value: AuditDatePreset; label: string }[] = [
  { value: "all", label: "全部时间" },
  { value: "today", label: "今天" },
  { value: "7d", label: "近 7 天" },
  { value: "30d", label: "近 30 天" },
  { value: "custom", label: "自定义" },
];
