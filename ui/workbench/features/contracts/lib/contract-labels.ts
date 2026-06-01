/** 合同与收付款标签文案。 */

export const CONTRACT_STATUS_LABELS: Record<string, string> = {
  draft: "草稿",
  pending_sign: "待签署",
  signed: "已签署",
  active: "履约中",
  completed: "已完结",
  terminated: "已终止",
};

export const CONTRACT_STATUSES = [
  { key: "draft", label: "草稿" },
  { key: "pending_sign", label: "待签署" },
  { key: "signed", label: "已签署" },
  { key: "active", label: "履约中" },
  { key: "completed", label: "已完结" },
  { key: "terminated", label: "已终止" },
] as const;

export const CONTRACT_TYPE_LABELS: Record<string, string> = {
  service: "服务合同",
  nda: "保密协议",
  framework: "框架协议",
  other: "其他",
};

export const PAYMENT_STATUS_LABELS: Record<string, string> = {
  pending: "待收付",
  processing: "处理中",
  paid: "已结清",
  cancelled: "已取消",
};

export const PAYMENT_DIRECTION_LABELS: Record<string, string> = {
  in: "收款",
  out: "付款",
};

export function contractStatusBadgeClass(status: string): string {
  if (status === "active") return "bg-brand-light text-brand";
  if (status === "signed") return "bg-green-50 text-green-700";
  if (status === "terminated") return "bg-red-50 text-red-600";
  return "bg-surface-muted text-ink-muted";
}
