/** A2A 宿主表单共享校验（链路 §4）。 */

import type { A2aPeerRefInput, Agent } from "@/lib/types";
import { AGENT_PLANNER, AGENT_RUNTIME_MODE } from "@/lib/agent-config";

export type A2aHostFormValues = {
  name: string;
  description: string;
  system_prompt: string;
  prompt_template_id: string;
  model_config_id: string;
  a2a_peers: A2aPeerRefInput[];
  a2a_invoke_policy: "rules_then_plan" | "rules_only" | "plan_only";
};

export const AGENT_HOST_FORM_STEPS = [
  { title: "基本信息", subtitle: "A2A 互联宿主名称与说明" },
  { title: "编排模型", subtitle: "选择用于任务拆解与汇总的模型" },
  { title: "成员 Agent", subtitle: "绑定外部 A2A Agent 与规则" },
] as const;

const DEFAULT_HOST_PROMPT =
  "你是 A2A 互联宿主编排器。根据用户问题，从已绑定的外部 Agent 中选择合适的成员委派任务，并综合各成员返回结果给出最终回答。";

export function emptyHostAgentForm(): A2aHostFormValues {
  return {
    name: "",
    description: "",
    system_prompt: DEFAULT_HOST_PROMPT,
    prompt_template_id: "",
    model_config_id: "",
    a2a_peers: [],
    a2a_invoke_policy: "rules_then_plan",
  };
}

export function agentToHostFormValues(agent: Agent): A2aHostFormValues {
  const cfg = (agent.config ?? {}) as Record<string, unknown>;
  return {
    name: agent.name,
    description: agent.description ?? "",
    system_prompt: agent.system_prompt ?? DEFAULT_HOST_PROMPT,
    prompt_template_id: agent.prompt_template_id ?? "",
    model_config_id: agent.model_config_id ?? "",
    a2a_peers: (agent.a2a_peers ?? []).map((p) => ({
      peer_id: p.id,
      role_hint: p.role_hint ?? undefined,
      trigger_keywords: p.trigger_keywords ?? [],
      enabled: p.enabled !== false,
    })),
    a2a_invoke_policy:
      (cfg.a2a_invoke_policy as A2aHostFormValues["a2a_invoke_policy"]) || "rules_then_plan",
  };
}

export function buildHostAgentConfig(
  form: A2aHostFormValues,
  base: Record<string, unknown>,
): Record<string, unknown> {
  return {
    ...base,
    a2a_invoke_policy: form.a2a_invoke_policy,
    max_a2a_calls_per_turn: Number(base.max_a2a_calls_per_turn ?? 3),
    runtime_mode: AGENT_RUNTIME_MODE.AUTONOMOUS,
    planner: AGENT_PLANNER.A2A_ORCHESTRATOR,
  };
}
