const LABELS: Record<string, string> = {
  pending: "排队中",
  parsing: "解析中",
  embedding: "向量化中",
  ready: "可检索",
  parse_failed: "解析失败",
  embed_failed: "向量化失败",
};

export type DocumentStatusTone = "success" | "progress" | "error" | "neutral";

const TONES: Record<string, DocumentStatusTone> = {
  pending: "progress",
  parsing: "progress",
  embedding: "progress",
  ready: "success",
  parse_failed: "error",
  embed_failed: "error",
};

export function documentStatusLabel(status: string): string {
  return LABELS[status] ?? status;
}

export function documentStatusTone(status: string): DocumentStatusTone {
  return TONES[status] ?? "neutral";
}

export function isDocumentProcessing(status: string): boolean {
  return status === "pending" || status === "parsing" || status === "embedding";
}

/** 入库失败后可重新提交 Celery 任务 */
export function canRetryDocument(status: string): boolean {
  return status === "parse_failed" || status === "embed_failed";
}

export function isDocumentFailed(status: string): boolean {
  return status === "parse_failed" || status === "embed_failed";
}
