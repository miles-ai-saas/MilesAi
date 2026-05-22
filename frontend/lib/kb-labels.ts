export function retrievalModeLabel(mode?: string | null): string {
  if (mode === "hybrid") return "混合检索";
  return "语义向量";
}

export const SEARCH_SOURCE_LABEL: Record<string, string> = {
  api: "API 调试",
  agent: "智能体 RAG",
  flow: "流程",
  debug: "调试",
};

export const ATTACHMENT_PURPOSE_LABEL: Record<string, string> = {
  general: "通用",
  chat: "对话",
  agent: "智能体",
  flow: "流程",
};
