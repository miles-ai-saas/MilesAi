export const OPPORTUNITY_STAGES = [
  { key: "prospecting", label: "线索" },
  { key: "qualification", label: "资质确认" },
  { key: "proposal", label: "方案报价" },
  { key: "negotiation", label: "谈判" },
  { key: "won", label: "赢单" },
  { key: "lost", label: "丢单" },
] as const;

export const OPPORTUNITY_STAGE_LABELS: Record<string, string> = Object.fromEntries(
  OPPORTUNITY_STAGES.map((s) => [s.key, s.label]),
);

export const QUOTE_STATUS_LABELS: Record<string, string> = {
  draft: "草稿",
  sent: "已发送",
  accepted: "已接受",
  rejected: "已拒绝",
  expired: "已过期",
};

export function stageBadgeClass(stage: string): string {
  if (stage === "won") return "bg-green-50 text-green-700";
  if (stage === "lost") return "bg-red-50 text-red-600";
  if (stage === "negotiation") return "bg-amber-50 text-amber-700";
  return "bg-brand-light text-brand";
}
