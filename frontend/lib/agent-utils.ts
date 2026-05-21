import type { Agent, Flow, ModelConfig, PromptTemplate } from "@/lib/types";

const DEFAULT_SYSTEM_PROMPT = "你是企业智能助手，请准确、简洁地回答用户问题。";

export function agentStatusLabel(status: string): string {
  return status === "enabled" ? "启用" : "禁用";
}

export function agentModeLabel(agent: Agent): string {
  const subs = agent.sub_agents?.length ?? 0;
  if (subs > 0) return `协同 · ${subs} 子智能体`;
  if (agent.published_flow_id) return "流程";
  if (agent.kb_ids.length > 0) return `RAG · ${agent.kb_ids.length} KB`;
  return "直连";
}

export function subAgentRoleLabel(roleHint?: string | null): string {
  const hit = SUB_AGENT_ROLE_OPTIONS.find((o) => o.value === (roleHint ?? ""));
  return hit?.label ?? roleHint ?? "未指定";
}

export const SUB_AGENT_ROLE_OPTIONS = [
  { value: "", label: "未指定" },
  { value: "retrieval", label: "检索" },
  { value: "ocr", label: "OCR" },
  { value: "summary", label: "总结" },
  { value: "compliance", label: "合规" },
  { value: "custom", label: "自定义" },
] as const;

export function buildCreateAgentPayload(
  total: number,
  opts: {
    flows: Flow[];
    prompts: PromptTemplate[];
    models: ModelConfig[];
  },
) {
  return {
    name: `助手 ${total + 1}`,
    kb_ids: [] as string[],
    published_flow_id: opts.flows[0]?.id,
    prompt_template_id: opts.prompts[0]?.id,
    model_config_id: opts.models[0]?.id,
    system_prompt: opts.prompts[0] ? undefined : DEFAULT_SYSTEM_PROMPT,
  };
}
