/**
 * 知识库文档入库状态：文案来自 `GET /kb/meta` 的 `document_statuses`（`KbMeta`），
 * 经 `documentStatusLabel(status, meta?.document_statuses)` 消费；色调/重试逻辑仍在前端。
 * 链路见 `lib/chains.ts` §8、`lib/enum-meta.ts`。
 */

import type { EnumOption } from "@/lib/enum-meta";
import { optionLabel } from "@/lib/enum-meta";

const FALLBACK_LABELS: Record<string, string> = {
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

export function documentStatusLabel(status: string, options?: EnumOption[]): string {
  return optionLabel(options, status) || FALLBACK_LABELS[status] || status;
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
