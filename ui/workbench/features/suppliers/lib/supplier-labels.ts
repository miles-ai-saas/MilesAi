/** 供应商标签与枚举文案。 */

export const SUPPLIER_CATEGORIES = [
  { key: "print", label: "印刷" },
  { key: "video", label: "影视拍摄" },
  { key: "construction", label: "搭建施工" },
  { key: "event", label: "活动执行" },
  { key: "design", label: "设计外包" },
  { key: "logistics", label: "物流运输" },
  { key: "other", label: "其他" },
] as const;

export const SUPPLIER_CATEGORY_LABELS: Record<string, string> = Object.fromEntries(
  SUPPLIER_CATEGORIES.map((c) => [c.key, c.label]),
);

export const SUPPLIER_STATUS_LABELS: Record<string, string> = {
  active: "合作中",
  inactive: "暂停合作",
  blacklisted: "黑名单",
};

export const PROJECT_SUPPLIER_STATUS_LABELS: Record<string, string> = {
  active: "进行中",
  completed: "已完成",
  cancelled: "已取消",
};

export function supplierStatusBadgeClass(status: string): string {
  if (status === "active") return "bg-emerald-50 text-emerald-700";
  if (status === "blacklisted") return "bg-red-50 text-red-600";
  return "bg-surface-muted text-ink-muted";
}

export const SUPPLIER_STATUSES = [
  { key: "active", label: "合作中" },
  { key: "inactive", label: "暂停合作" },
  { key: "blacklisted", label: "黑名单" },
] as const;
