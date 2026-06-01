/** 客户标签与枚举文案。 */

export const CLIENT_INDUSTRIES = [
  { key: "government", label: "政府机关" },
  { key: "enterprise", label: "企业" },
  { key: "park", label: "园区" },
  { key: "commercial", label: "商业综合体" },
  { key: "tourism", label: "文旅" },
  { key: "other", label: "其他" },
] as const;

export const CLIENT_INDUSTRY_LABELS: Record<string, string> = Object.fromEntries(
  CLIENT_INDUSTRIES.map((c) => [c.key, c.label]),
);

export const CLIENT_CONFIDENTIALITY_LABELS: Record<string, string> = {
  normal: "普通",
  internal: "内部",
  restricted: "涉密",
};

export function clientConfBadgeClass(level: string): string {
  if (level === "restricted") return "bg-red-50 text-red-600";
  if (level === "internal") return "bg-amber-50 text-amber-700";
  return "bg-surface-muted text-ink-muted";
}
