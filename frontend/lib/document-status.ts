const LABELS: Record<string, string> = {
  pending: "排队中",
  parsing: "解析中",
  embedding: "向量化中",
  ready: "已完成",
  parse_failed: "解析失败",
  embed_failed: "向量化失败",
};

export function documentStatusLabel(status: string): string {
  return LABELS[status] ?? status;
}

export function canRetryDocument(status: string): boolean {
  return status === "parse_failed" || status === "embed_failed" || status === "ready";
}
