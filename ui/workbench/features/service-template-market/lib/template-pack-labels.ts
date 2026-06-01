/** 模板包状态与发布方文案。 */

export const PACK_PUBLISHER_LABELS: Record<string, string> = {
  platform: "平台官方",
  partner: "合作伙伴",
  tenant: "租户分享",
};

export const PACK_STATUS_LABELS: Record<string, string> = {
  draft: "草稿",
  pending_review: "待审核",
  published: "已上架",
  rejected: "已驳回",
};

export const PACK_STATUS_COLORS: Record<string, string> = {
  draft: "bg-surface-muted text-ink-muted",
  pending_review: "bg-amber-50 text-amber-700",
  published: "bg-emerald-50 text-emerald-700",
  rejected: "bg-red-50 text-red-600",
};
