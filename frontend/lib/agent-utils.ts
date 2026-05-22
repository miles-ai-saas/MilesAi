import type { Agent, Flow, ModelConfig, PromptTemplate } from "@/lib/types";

const DEFAULT_SYSTEM_PROMPT = "你是企业智能助手，请准确、简洁地回答用户问题。";

export function agentStatusLabel(status: string): string {
  return status === "enabled" ? "启用" : "禁用";
}

export function agentTypeLabel(agent: Agent): string {
  return agent.agent_type === "a2a" ? "A2A 互联宿主" : "平台内";
}

export function agentModeLabel(agent: Agent): string {
  if (agent.agent_type === "a2a") {
    const n =
      agent.a2a_peers?.filter((p) => p.enabled !== false).length ??
      Number((agent.config as Record<string, unknown> | undefined)?.a2a_host_peer_count ?? 0);
    return n > 0 ? `外部编排 · ${n} 个成员` : "外部编排 · 未绑成员";
  }
  const a2a =
    agent.a2a_peers?.filter((p) => p.enabled !== false).length ??
    Number((agent.config as Record<string, unknown> | undefined)?.a2a_peer_count ?? 0);
  const subs = agent.sub_agents?.length ?? 0;
  const parts: string[] = [];
  if (subs > 0) parts.push(`内部协同 · ${subs}`);
  if (a2a > 0) parts.push(`外部引用 · ${a2a}`);
  if (parts.length) return parts.join(" · ");
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
