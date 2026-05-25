import type { A2aPeerRefInput, SubAgentBindingInput } from "@/lib/types";
import type { Agent } from "@/lib/types";

export type AgentFormValues = {
  name: string;
  description: string;
  category_id: string;
  tag_ids: string[];
  system_prompt: string;
  kb_ids: string[];
  published_flow_id: string;
  prompt_template_id: string;
  model_config_id: string;
  skill_package_id: string;
  mcp_service_ids: string[];
  sub_agents: SubAgentBindingInput[];
  a2a_peers: A2aPeerRefInput[];
  a2a_invoke_policy: "rules_then_plan" | "rules_only" | "plan_only";
  use_langgraph_rag: boolean;
  use_llm_grade: boolean;
  relevance_threshold: number;
  rag_max_retries: number;
  subagent_parallel: boolean;
  force_platform_planner: boolean;
};

export const AGENT_FORM_STEPS = [
  {
    title: "基本信息",
    subtitle: "配置智能体的基本信息",
  },
  {
    title: "模型与提示词",
    subtitle: "选择模型和提示词模版",
  },
  {
    title: "工具与能力",
    subtitle: "配置技能包、编排流程与 MCP 服务",
  },
  {
    title: "知识库与内部协同",
    subtitle: "知识库、内部协同与外部 A2A 引用（规则触发 + 自动规划）",
  },
  {
    title: "高级设置",
    subtitle: "配置 RAG 工作流与内部协同规划选项",
  },
] as const;

export function emptyAgentForm(): AgentFormValues {
  return {
    name: "",
    description: "",
    category_id: "",
    tag_ids: [],
    system_prompt: "",
    kb_ids: [],
    published_flow_id: "",
    prompt_template_id: "",
    model_config_id: "",
    skill_package_id: "",
    mcp_service_ids: [],
    sub_agents: [],
    a2a_peers: [],
    a2a_invoke_policy: "rules_then_plan",
    use_langgraph_rag: true,
    use_llm_grade: false,
    relevance_threshold: 0.35,
    rag_max_retries: 1,
    subagent_parallel: false,
    force_platform_planner: false,
  };
}

export function agentToFormValues(agent: Agent): AgentFormValues {
  const cfg = (agent.config ?? {}) as Record<string, unknown>;
  return {
    name: agent.name,
    description: agent.description ?? "",
    category_id: agent.category_id ?? "",
    tag_ids: (agent.tags ?? []).map((t) => t.id),
    system_prompt: agent.system_prompt ?? "",
    kb_ids: agent.kb_ids ?? [],
    published_flow_id: agent.published_flow_id ?? "",
    prompt_template_id: agent.prompt_template_id ?? "",
    model_config_id: agent.model_config_id ?? "",
    skill_package_id: String(cfg.skill_package_id ?? ""),
    mcp_service_ids: ((cfg.mcp_service_ids as string[]) ?? []).map(String),
    sub_agents: (agent.sub_agents ?? []).map((s) => ({
      child_agent_id: s.id,
      role_hint: s.role_hint ?? undefined,
    })),
    a2a_peers: (agent.a2a_peers ?? []).map((p) => ({
      peer_id: p.id,
      role_hint: p.role_hint ?? undefined,
      trigger_keywords: p.trigger_keywords ?? [],
      enabled: p.enabled !== false,
    })),
    a2a_invoke_policy:
      (cfg.a2a_invoke_policy as AgentFormValues["a2a_invoke_policy"]) || "rules_then_plan",
    use_langgraph_rag: cfg.use_langgraph_rag !== false,
    relevance_threshold: Number(cfg.relevance_threshold ?? 0.35),
    rag_max_retries: Number(cfg.rag_max_retries ?? 1),
    use_llm_grade: Boolean(cfg.use_llm_grade),
    subagent_parallel: Boolean(cfg.subagent_parallel),
    force_platform_planner: Boolean(cfg.force_platform_planner),
  };
}

export function formatAgentCode(agentId: string): string {
  const year = new Date().getFullYear();
  const short = agentId.replace(/-/g, "").slice(0, 4).toUpperCase();
  return `AGENT-${year}-${short}`;
}

export function buildAgentConfig(
  form: AgentFormValues,
  baseConfig: Record<string, unknown> | undefined,
): Record<string, unknown> {
  const config: Record<string, unknown> = { ...(baseConfig ?? {}) };
  delete config.agent_tag;
  if (form.skill_package_id) config.skill_package_id = form.skill_package_id;
  else delete config.skill_package_id;
  if (form.mcp_service_ids.length) config.mcp_service_ids = form.mcp_service_ids;
  else delete config.mcp_service_ids;

  if (form.sub_agents.length > 0) {
    config.runtime_mode = "autonomous";
    config.planner = "deepagents";
    config.max_plan_iterations = Number(config.max_plan_iterations ?? 12);
    config.max_subagent_calls = Number(config.max_subagent_calls ?? 20);
    if (form.subagent_parallel) config.subagent_parallel = true;
    else delete config.subagent_parallel;
    if (form.force_platform_planner) config.force_platform_planner = true;
    else delete config.force_platform_planner;
    delete config.use_langgraph_rag;
    delete config.use_llm_grade;
  } else if (form.kb_ids.length > 0) {
    if (!form.published_flow_id) delete config.runtime_mode;
    if (form.use_langgraph_rag) delete config.use_langgraph_rag;
    else config.use_langgraph_rag = false;
    config.relevance_threshold = form.relevance_threshold;
    config.rag_max_retries = form.rag_max_retries;
    if (form.use_llm_grade) config.use_llm_grade = true;
    else delete config.use_llm_grade;
  } else {
    if (!form.published_flow_id) delete config.runtime_mode;
    delete config.use_langgraph_rag;
    delete config.relevance_threshold;
    delete config.rag_max_retries;
    delete config.use_llm_grade;
  }

  if (form.a2a_peers.length > 0) {
    config.a2a_invoke_policy = form.a2a_invoke_policy;
    config.max_a2a_calls_per_turn = Number(config.max_a2a_calls_per_turn ?? 2);
  } else {
    delete config.a2a_invoke_policy;
    delete config.max_a2a_calls_per_turn;
    delete config.a2a_peer_count;
  }

  if (form.published_flow_id) {
    config.runtime_mode = "workflow";
  } else if (config.runtime_mode === "workflow") {
    delete config.runtime_mode;
  }
  return config;
}
