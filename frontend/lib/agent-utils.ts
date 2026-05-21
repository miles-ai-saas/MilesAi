import type { Agent, Flow, ModelConfig, PromptTemplate } from "@/lib/types";

const DEFAULT_SYSTEM_PROMPT = "你是企业智能助手，请准确、简洁地回答用户问题。";

export function agentModeLabel(agent: Agent): string {
  if (agent.published_flow_id) return "流程";
  if (agent.kb_ids.length > 0) return `RAG · ${agent.kb_ids.length} KB`;
  return "直连";
}

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
