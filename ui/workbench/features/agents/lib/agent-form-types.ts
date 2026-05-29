/** 智能体表单类型与默认值（链路 §3）。 */

import type { A2aPeerRefInput, SubAgentBindingInput } from "@/lib/types";

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
  enable_tool_calling: boolean;
  tool_slugs: string[];
  enable_generative_tools: boolean;
  generative_image_model_id: string;
  generative_video_model_id: string;
  carry_forward_media: boolean;
};

export const AGENT_FORM_STEPS = [
  { title: "基本信息", subtitle: "配置智能体的基本信息" },
  { title: "模型与提示词", subtitle: "选择模型和提示词模版" },
  { title: "工具与能力", subtitle: "配置技能包、平台工具、编排流程与 MCP 服务" },
  { title: "知识库与内部协同", subtitle: "知识库、内部协同与外部 A2A 引用（规则触发 + 自动规划）" },
  { title: "高级设置", subtitle: "配置 RAG 工作流与内部协同规划选项" },
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
    enable_tool_calling: false,
    tool_slugs: [],
    enable_generative_tools: false,
    generative_image_model_id: "",
    generative_video_model_id: "",
    carry_forward_media: true,
  };
}
