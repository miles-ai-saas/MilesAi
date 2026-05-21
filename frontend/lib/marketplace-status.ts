const LABELS: Record<string, string> = {
  draft: "草稿",
  pending_review: "待审核",
  published: "已上架",
  rejected: "已驳回",
  archived: "已下架",
};

export function marketplaceStatusLabel(status: string): string {
  return LABELS[status] ?? status;
}
