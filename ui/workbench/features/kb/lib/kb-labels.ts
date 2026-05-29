/**
 * 知识库展示文案：优先 `GET /kb/meta`（`useKbMeta`），未加载时本地 fallback。
 * 文档状态见 `document-status.ts`（`meta.document_statuses`）。链路见 `lib/enum-meta.ts`。；链路 §4 见 lib/chains.ts。
 */

import type { EnumOption } from "@/lib/enum-meta";
import { optionLabel } from "@/lib/enum-meta";

const FALLBACK_RETRIEVAL: Record<string, string> = {
  vector: "纯语义向量",
  hybrid: "混合检索",
};

const FALLBACK_SEARCH_SOURCE: Record<string, string> = {
  api: "API 调试",
  agent: "智能体 RAG",
  flow: "流程",
  debug: "调试",
};

export function retrievalModeLabel(mode?: string | null, modes?: EnumOption[]): string {
  if (!mode) return "—";
  return optionLabel(modes, mode) || FALLBACK_RETRIEVAL[mode] || mode;
}

export function searchSourceLabel(source: string, sources?: EnumOption[]): string {
  return optionLabel(sources, source) || FALLBACK_SEARCH_SOURCE[source] || source;
}
