/** 智能体对话调用记录展示文案。 */

const STATUS_LABELS: Record<string, string> = {
  success: "成功",
  failed: "失败",
  blocked: "已拦截",
};

const ROUTE_LABELS: Record<string, string> = {
  a2a_host: "A2A 宿主",
  subagent: "子智能体",
  a2a_augmented: "A2A 增强",
  flow: "流程画布",
  rag: "RAG",
  tool_agent: "工具调用",
  direct_llm: "直连模型",
  unknown: "未知",
};

export function agentCallStatusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

export function agentCallRouteLabel(route: string): string {
  return ROUTE_LABELS[route] ?? route;
}

export function formatCallRecordTime(iso: string): string {
  return new Date(iso).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function shortenTraceId(traceId: string | null | undefined): string {
  if (!traceId) return "—";
  if (traceId.length <= 12) return traceId;
  return `${traceId.slice(0, 8)}…`;
}

export const CALL_RECORD_STATUS_CHIPS = [
  { value: "", label: "全部" },
  { value: "success", label: "成功" },
  { value: "failed", label: "失败" },
  { value: "blocked", label: "已拦截" },
] as const;

export function hookTriggerLabel(trigger: string): string {
  const labels: Record<string, string> = {
    before_call: "调用前",
    after_call: "调用后",
    before_reasoning: "推理前",
    after_reasoning: "推理后",
    before_tool: "工具前",
    after_tool: "工具后",
    on_error: "错误",
  };
  return labels[trigger] ?? trigger;
}
