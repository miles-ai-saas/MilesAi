import { AGENT_PLANNER, AGENT_RUNTIME_MODE } from "@/features/agents/lib/agent-config";
import type { AgentFormValues } from "@/features/agents/lib/agent-form-types";
import type { Agent } from "@/lib/types";

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
    a2a_invoke_policy: (cfg.a2a_invoke_policy as AgentFormValues["a2a_invoke_policy"]) || "rules_then_plan",
    use_langgraph_rag: cfg.use_langgraph_rag !== false,
    relevance_threshold: Number(cfg.relevance_threshold ?? 0.35),
    rag_max_retries: Number(cfg.rag_max_retries ?? 1),
    use_llm_grade: Boolean(cfg.use_llm_grade),
    subagent_parallel: Boolean(cfg.subagent_parallel),
    force_platform_planner: Boolean(cfg.force_platform_planner),
    enable_tool_calling: Boolean(cfg.enable_tool_calling),
    tool_slugs: ((cfg.tool_slugs as string[]) ?? []).map(String),
    enable_generative_tools: Boolean(cfg.enable_generative_tools),
    generative_image_model_id: String(cfg.generative_image_model_id ?? ""),
    generative_video_model_id: String(cfg.generative_video_model_id ?? ""),
    carry_forward_media: cfg.carry_forward_media !== false,
  };
}

export function formatAgentCode(agentId: string): string {
  const year = new Date().getFullYear();
  const short = agentId.replace(/-/g, "").slice(0, 4).toUpperCase();
  return `AGENT-${year}-${short}`;
}

export function buildAgentConfig(form: AgentFormValues, baseConfig: Record<string, unknown> | undefined): Record<string, unknown> {
  const config: Record<string, unknown> = { ...(baseConfig ?? {}) };
  delete config.agent_tag;
  if (form.skill_package_id) config.skill_package_id = form.skill_package_id;
  else delete config.skill_package_id;
  if (form.mcp_service_ids.length) config.mcp_service_ids = form.mcp_service_ids;
  else delete config.mcp_service_ids;

  if (form.enable_tool_calling) config.enable_tool_calling = true;
  else delete config.enable_tool_calling;
  if (form.tool_slugs.length) config.tool_slugs = form.tool_slugs;
  else delete config.tool_slugs;

  if (form.enable_generative_tools && form.enable_tool_calling) {
    config.enable_generative_tools = true;
  } else {
    delete config.enable_generative_tools;
  }
  if (form.generative_image_model_id) {
    config.generative_image_model_id = form.generative_image_model_id;
  } else {
    delete config.generative_image_model_id;
  }
  if (form.generative_video_model_id) {
    config.generative_video_model_id = form.generative_video_model_id;
  } else {
    delete config.generative_video_model_id;
  }

  if (form.sub_agents.length > 0) {
    config.runtime_mode = AGENT_RUNTIME_MODE.AUTONOMOUS;
    config.planner = AGENT_PLANNER.DEEPAGENTS;
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
    config.runtime_mode = AGENT_RUNTIME_MODE.WORKFLOW;
  } else if (config.runtime_mode === AGENT_RUNTIME_MODE.WORKFLOW) {
    delete config.runtime_mode;
  }

  if (!form.carry_forward_media) {
    config.carry_forward_media = false;
  } else {
    delete config.carry_forward_media;
  }

  return config;
}
