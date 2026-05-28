/** 知识库详情页共享常量与工具（见 app/workbench/kb/[id]/page.tsx）。 */

import { isDocumentProcessing } from "@/lib/document-status";

export type KbDetailTabKey = "documents" | "search" | "logs";
export type KbDocFilter = "all" | "ready" | "processing" | "failed";

export type KbDetailAlertState = { tone: "success" | "error" | "info"; message: string } | null;

export type KbSearchHit = {
  content: string;
  score: number;
  score_vector?: number | null;
  score_keyword?: number | null;
  score_rerank?: number | null;
  filename?: string;
  vector_type?: string | null;
  mime_type?: string | null;
};

export const KB_DETAIL_TABS: { key: KbDetailTabKey; label: string }[] = [
  { key: "documents", label: "文档" },
  { key: "search", label: "检索测试" },
  { key: "logs", label: "检索记录" },
];

export const KB_DOC_FILTERS: { key: KbDocFilter; label: string }[] = [
  { key: "all", label: "全部" },
  { key: "ready", label: "可检索" },
  { key: "processing", label: "处理中" },
  { key: "failed", label: "失败" },
];

export function matchKbDocFilter(status: string, filter: KbDocFilter): boolean {
  if (filter === "all") return true;
  if (filter === "ready") return status === "ready";
  if (filter === "processing") return isDocumentProcessing(status);
  if (filter === "failed") return status.includes("failed");
  return true;
}
