/**
 * 知识库展示文案：优先 GET /kb/meta，未加载时用本地 fallback。
 * 页面用 optionLabel(meta?.xxx, value)；约定见 docs/guides/hooks.md §9。
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

export function retrievalModeLabel(
  mode?: string | null,
  modes?: EnumOption[],
): string {
  if (!mode) return "—";
  return optionLabel(modes, mode) || FALLBACK_RETRIEVAL[mode] || mode;
}

/** @deprecated 优先使用 getKbMeta().search_sources */
export const SEARCH_SOURCE_LABEL: Record<string, string> = FALLBACK_SEARCH_SOURCE;

export function searchSourceLabel(source: string, sources?: EnumOption[]): string {
  return optionLabel(sources, source) || FALLBACK_SEARCH_SOURCE[source] || source;
}

/** @deprecated 使用 attachmentPurposeLabel(purpose, meta) */
export const ATTACHMENT_PURPOSE_LABEL: Record<string, string> = {
  general: "通用",
  chat: "对话",
  agent: "智能体",
  flow: "流程",
};
