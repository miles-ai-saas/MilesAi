const LABELS: Record<string, string> = {
  draft: "草稿",
  published: "已上架",
  archived: "已下架",
};

export function marketplaceStatusLabel(status: string): string {
  return LABELS[status] ?? status;
}
