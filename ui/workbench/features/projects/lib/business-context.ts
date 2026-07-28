/**
 * 业务中心 → AI 工作台跨分区上下文与 deep link。
 */

import type { BizProjectAiContext } from "@/lib/types";

const STORAGE_KEY = "miles:biz-context";

export type BusinessContext = {
  projectId: string;
  projectName: string;
  clientName: string;
  workPackageId?: string;
  workPackageName?: string;
  serviceLine?: string;
  serviceLineLabel?: string;
  contextText: string;
  chatHint?: string;
  ragEnabled: boolean;
  savedAt: number;
};

export function saveBusinessContext(ctx: Omit<BusinessContext, "savedAt">) {
  if (typeof window === "undefined") return;
  const payload: BusinessContext = { ...ctx, savedAt: Date.now() };
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

export function loadBusinessContext(): BusinessContext | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as BusinessContext;
    if (!parsed.projectId || !parsed.contextText) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function clearBusinessContext() {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(STORAGE_KEY);
}

export type AgentChatDeepLinkParams = {
  agentId?: string;
  projectId: string;
  workPackageId?: string;
  prompt?: string;
  bizContext?: Omit<BusinessContext, "savedAt">;
};

/** 构建智能体对话 deep link，并将业务上下文写入 sessionStorage。 */
export function buildAgentChatDeepLink(params: AgentChatDeepLinkParams): string {
  if (params.bizContext) {
    saveBusinessContext(params.bizContext);
  }
  const q = new URLSearchParams();
  if (params.agentId) q.set("agent", params.agentId);
  q.set("projectId", params.projectId);
  if (params.workPackageId) q.set("wpId", params.workPackageId);
  if (params.prompt) q.set("prompt", params.prompt);
  q.set("biz", "1");
  // 静态导出 trailingSlash: true
  return `/workbench/agents/chat/?${q.toString()}`;
}

export function buildFlowsDeepLink(flowTemplateId?: string): string {
  if (flowTemplateId) return `/workbench/flows?template=${encodeURIComponent(flowTemplateId)}`;
  return "/workbench/flows";
}

export function buildKbDeepLink(kbId?: string): string {
  if (kbId) return `/workbench/knowledge-base/${kbId}`;
  return "/workbench/knowledge-base";
}

/** 将业务上下文与用户输入合并为首条消息前缀（仅非涉密且存在上下文时）。 */
export function prependBusinessContext(userText: string, ctx: BusinessContext | null): string {
  if (!ctx || !ctx.ragEnabled) return userText;
  const header = `[项目上下文]\n${ctx.contextText}${ctx.chatHint ? `\n\n[协作提示]\n${ctx.chatHint}` : ""}\n\n[用户问题]\n`;
  return `${header}${userText}`;
}

/** API AI 上下文 → sessionStorage 业务上下文。 */
export function projectAiContextToStored(
  ctx: BizProjectAiContext,
  rec?: BizProjectAiContext["recommendations"][number],
): Omit<BusinessContext, "savedAt"> {
  return {
    projectId: ctx.project_id,
    projectName: ctx.project_name,
    clientName: ctx.client_name,
    workPackageId: rec?.work_package_id,
    workPackageName: rec?.work_package_name,
    serviceLine: rec?.service_line,
    serviceLineLabel: rec?.service_line_label,
    contextText: ctx.context_text,
    chatHint: rec?.chat_hint,
    ragEnabled: ctx.rag_enabled,
  };
}
