import { describe, it, expect } from "vitest";
import { emptyAgentForm, agentToFormValues, buildAgentConfig, formatAgentCode } from "@/features/agents/lib/agent-form-types";
import type { Agent, AgentConfig } from "@/lib/types";

function mockAgent(overrides: Partial<Agent> = {}): Agent {
  return {
    id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    name: "测试智能体",
    description: "一个测试",
    category_id: "cat-1",
    tags: [{ id: "tag-1", name: "标签1" }],
    system_prompt: "你是一个助手",
    kb_ids: ["kb-1"],
    published_flow_id: "flow-1",
    prompt_template_id: "pt-1",
    model_config_id: "model-1",
    config: {} as AgentConfig,
    sub_agents: [],
    a2a_peers: [],
    agent_type: "custom" as const,
    status: "enabled" as const,
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-01T00:00:00Z",
    ...overrides,
  } as Agent;
}

describe("emptyAgentForm", () => {
  it("返回所有字段的默认值", () => {
    const form = emptyAgentForm();
    expect(form.name).toBe("");
    expect(form.a2a_invoke_policy).toBe("rules_then_plan");
    expect(form.use_langgraph_rag).toBe(true);
    expect(form.relevance_threshold).toBe(0.35);
    expect(form.rag_max_retries).toBe(1);
    expect(form.carry_forward_media).toBe(true);
    expect(form.sub_agents).toEqual([]);
    expect(form.a2a_peers).toEqual([]);
    expect(form.tool_slugs).toEqual([]);
  });
});

describe("agentToFormValues", () => {
  it("将 Agent 对象转换为表单值", () => {
    const agent = mockAgent();
    const form = agentToFormValues(agent);
    expect(form.name).toBe("测试智能体");
    expect(form.description).toBe("一个测试");
    expect(form.kb_ids).toEqual(["kb-1"]);
    expect(form.published_flow_id).toBe("flow-1");
    expect(form.tag_ids).toEqual(["tag-1"]);
  });

  it("读取 config.skill_ids 多技能绑定，并兼容旧版单值键", () => {
    const listForm = agentToFormValues(mockAgent({ config: { skill_ids: ["sk-1", "sk-2"], mcp_service_ids: ["mcp-1", "mcp-2"] } as AgentConfig }));
    expect(listForm.skill_ids).toEqual(["sk-1", "sk-2"]);
    expect(listForm.mcp_service_ids).toEqual(["mcp-1", "mcp-2"]);

    const legacyForm = agentToFormValues(mockAgent({ config: { skill_package_id: "sk-old" } as AgentConfig }));
    expect(legacyForm.skill_ids).toEqual(["sk-old"]);
  });

  it("默认 carry_forward_media 为 true", () => {
    const agent = mockAgent({ config: {} as AgentConfig });
    expect(agentToFormValues(agent).carry_forward_media).toBe(true);
  });

  it("carry_forward_media 显式 false 时保持 false", () => {
    const agent = mockAgent({ config: { carry_forward_media: false } as AgentConfig });
    expect(agentToFormValues(agent).carry_forward_media).toBe(false);
  });

  it("处理空 agent 描述和 prompt", () => {
    const agent = mockAgent({ description: null as unknown as string, system_prompt: null as unknown as string });
    const form = agentToFormValues(agent);
    expect(form.description).toBe("");
    expect(form.system_prompt).toBe("");
  });
});

describe("buildAgentConfig", () => {
  it("无子智能体且无 KB 时清除 RAG 配置", () => {
    const form = emptyAgentForm();
    // name 必须非空，但 buildAgentConfig 不校验 name
    form.kb_ids = [];
    form.sub_agents = [];
    const config = buildAgentConfig(form, undefined);
    expect(config.use_langgraph_rag).toBeUndefined();
    expect(config.relevance_threshold).toBeUndefined();
    expect(config.rag_max_retries).toBeUndefined();
    expect(config.use_llm_grade).toBeUndefined();
  });

  it("有 KB 时保留 RAG 配置", () => {
    const form = { ...emptyAgentForm(), kb_ids: ["kb-1"], relevance_threshold: 0.5, rag_max_retries: 3 };
    const config = buildAgentConfig(form, undefined);
    expect(config.relevance_threshold).toBe(0.5);
    expect(config.rag_max_retries).toBe(3);
  });

  it("有子智能体时设置 DeepAgents 运行时", () => {
    const form = {
      ...emptyAgentForm(),
      sub_agents: [{ child_agent_id: "agent-1" }],
      subagent_parallel: true,
    };
    const config = buildAgentConfig(form, undefined);
    expect(config.runtime_mode).toBe("autonomous");
    expect(config.planner).toBe("deepagents");
    expect(config.subagent_parallel).toBe(true);
  });

  it("有 a2a_peers 时设置 invoke_policy", () => {
    const form = {
      ...emptyAgentForm(),
      a2a_peers: [{ peer_id: "peer-1", role_hint: "help", trigger_keywords: ["help"], enabled: true }],
      a2a_invoke_policy: "rules_only" as const,
    };
    const config = buildAgentConfig(form, undefined);
    expect(config.a2a_invoke_policy).toBe("rules_only");
    expect(config.max_a2a_calls_per_turn).toBe(2);
  });

  it("有 published_flow_id 时设置 workflow 模式", () => {
    const form = { ...emptyAgentForm(), published_flow_id: "flow-1" };
    const config = buildAgentConfig(form, undefined);
    expect(config.runtime_mode).toBe("workflow");
  });

  it("carry_forward_media=false 保留在 config 中", () => {
    const form = { ...emptyAgentForm(), carry_forward_media: false };
    const config = buildAgentConfig(form, undefined);
    expect(config.carry_forward_media).toBe(false);
  });

  it("carry_forward_media=true 从 config 中删除", () => {
    const form = { ...emptyAgentForm(), carry_forward_media: true };
    const config = buildAgentConfig(form, undefined);
    expect(config.carry_forward_media).toBeUndefined();
  });

  it("enable_generative_tools 仅在 enable_tool_calling 为 true 时生效", () => {
    const formOn = { ...emptyAgentForm(), enable_tool_calling: true, enable_generative_tools: true };
    expect(buildAgentConfig(formOn, undefined).enable_generative_tools).toBe(true);
    const formOff = { ...emptyAgentForm(), enable_tool_calling: false, enable_generative_tools: true };
    expect(buildAgentConfig(formOff, undefined).enable_generative_tools).toBeUndefined();
  });

  it("generative image/video model_id 仅在非空时写入", () => {
    const form = { ...emptyAgentForm(), enable_tool_calling: true, enable_generative_tools: true, generative_image_model_id: "img-1" };
    const config = buildAgentConfig(form, undefined);
    expect(config.generative_image_model_id).toBe("img-1");
    expect(config.generative_video_model_id).toBeUndefined();
  });

  it("保留 baseConfig 中的其他字段", () => {
    const base: AgentConfig = { custom_field: "keep", agent_tag: "remove-me" };
    const config = buildAgentConfig(emptyAgentForm(), base);
    expect(config.custom_field).toBe("keep");
    expect(config.agent_tag).toBeUndefined();
  });

  it("skill_ids 非空时写入，并把旧版单值键迁移掉", () => {
    const form = { ...emptyAgentForm(), skill_ids: ["sk-1", "sk-2"] };
    const config = buildAgentConfig(form, { skill_package_id: "sk-old" } as AgentConfig);
    expect(config.skill_ids).toEqual(["sk-1", "sk-2"]);
    expect(config.skill_package_id).toBeUndefined();
  });

  it("skill_ids 为空时不写入", () => {
    const config = buildAgentConfig(emptyAgentForm(), undefined);
    expect(config.skill_ids).toBeUndefined();
  });
});

describe("formatAgentCode", () => {
  it("生成 AGENT-YYYY-XXXX 格式的编号", () => {
    const code = formatAgentCode("a1b2c3d4-e5f6-7890-abcd-ef1234567890");
    expect(code).toMatch(/^AGENT-\d{4}-A1B2$/);
  });
});
