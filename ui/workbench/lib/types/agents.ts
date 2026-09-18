/** 域类型：与 backend OpenAPI 对齐。 */

import type { EnumOption } from "@/lib/enum-meta";
import type { A2aPeerRef } from "./a2a";
import type { FlowGraph } from "./flows";
import type { TagRef } from "./tags";
export interface SubAgentRef {
  id: string;
  name: string;
  role_hint?: string | null;
  status: string;
  description?: string | null;
}

export interface SubAgentBindingInput {
  child_agent_id: string;
  role_hint?: string | null;
}

export type AgentType = "custom" | "a2a";

export interface Agent {
  id: string;
  agent_type?: AgentType;
  category_id?: string | null;
  category_name?: string | null;
  tags?: TagRef[];
  name: string;
  description?: string | null;
  status: string;
  kb_ids: string[];
  sub_agents?: SubAgentRef[];
  a2a_peers?: A2aPeerRef[];
  published_flow_id?: string | null;
  model_config_id?: string | null;
  prompt_template_id?: string | null;
  system_prompt?: string | null;
  config?: AgentConfig;
}

/** 智能体 config 字段（与 backend schemas/agent.py 对齐，所有字段可选以兼容增量更新）。 */
export interface AgentConfig {
  /** 绑定的技能包 ID 列表（多技能绑定）。 */
  skill_ids?: string[];
  /** @deprecated 旧版单技能键；后端仍兼容读取，保存时会迁移为 `skill_ids`。 */
  skill_package_id?: string;
  mcp_service_ids?: string[];
  a2a_invoke_policy?: "rules_then_plan" | "rules_only" | "plan_only";
  use_langgraph_rag?: boolean;
  relevance_threshold?: number;
  rag_max_retries?: number;
  use_llm_grade?: boolean;
  subagent_parallel?: boolean;
  force_platform_planner?: boolean;
  enable_tool_calling?: boolean;
  tool_slugs?: string[];
  enable_generative_tools?: boolean;
  generative_image_model_id?: string;
  generative_video_model_id?: string;
  carry_forward_media?: boolean;
  runtime_mode?: string;
  planner?: string;
  max_plan_iterations?: number;
  max_subagent_calls?: number;
  max_a2a_calls_per_turn?: number;
  a2a_peer_count?: number;
  a2a_host_peer_count?: number;
  /** 保留后端可能返回的未登记字段 */
  [key: string]: unknown;
}

export interface AgentStatsPoint {
  date: string;
  value: number;
}

export interface AgentStats {
  days: number;
  sessions_total: number;
  active_users_total: number;
  messages_total: number;
  avg_rounds_total: number;
  sessions_by_day: AgentStatsPoint[];
  active_users_by_day: AgentStatsPoint[];
  messages_by_day: AgentStatsPoint[];
  avg_rounds_by_day: AgentStatsPoint[];
}

export type AgentPrimaryPath =
  | "a2a_host"
  | "subagent_orchestration"
  | "a2a_augmented"
  | "flow"
  | "tool_calling"
  | "rag_graph"
  | "rag_legacy"
  | "rag_retrieve_only"
  | "direct";

export interface AgentArchitectureDecisionStep {
  id: string;
  label: string;
  description?: string | null;
  active: boolean;
}

export interface AgentArchitectureAttachments {
  model?: { id: string; name: string } | null;
  kbs: { id: string; name: string }[];
  sub_agents: { id: string; name: string; role_hint?: string | null }[];
  a2a_peers: { id: string; name: string; role_hint?: string | null; enabled: boolean }[];
  flow?: {
    id: string;
    name: string;
    version: number;
    status: string;
    is_runtime_path: boolean;
  } | null;
}

export interface AgentArchitecture {
  agent_id: string;
  primary_path: AgentPrimaryPath;
  primary_path_label: string;
  decision_steps: AgentArchitectureDecisionStep[];
  attachments: AgentArchitectureAttachments;
  flow_graph?: FlowGraph | null;
}

export interface AgentSchedule {
  id: string;
  agent_id: string;
  content: string;
  cron: string;
  cron_description: string;
  enabled: boolean;
  last_run_at?: string | null;
  next_run_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentScheduleInput {
  content: string;
  cron: string;
  enabled?: boolean;
}

export interface AgentScheduleRun {
  id: string;
  schedule_id: string;
  agent_id: string;
  status: "success" | "failed";
  started_at: string;
  finished_at?: string | null;
  error_message?: string | null;
}

export interface AgentCallRecord {
  id: string;
  agent_id: string;
  conversation_id?: string | null;
  trace_id?: string | null;
  actor_user_id?: string | null;
  actor_username?: string | null;
  status: string;
  route: string;
  query_preview: string;
  answer_preview: string;
  latency_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
  step_count: number;
  tool_call_count: number;
  error_code?: string | null;
  error_message?: string | null;
  created_at: string;
}

export interface AgentCallRecordDetail extends AgentCallRecord {
  meta?: Record<string, unknown>;
  steps_summary?: { type?: string; label?: string }[] | null;
  related_tool_logs?: ToolInvocationLog[];
  related_hook_logs?: AgentCallRecordHookLog[];
}

export interface AgentCallRecordHookLog {
  id: string;
  hook_id: string;
  trace_id?: string | null;
  trigger: string;
  scope: string;
  status: string;
  duration_ms?: number | null;
  error_message?: string | null;
  created_at: string;
}

export interface AgentChatSessionMessage {
  id: string;
  role: string;
  content: string;
  sort_index: number;
  media?: { attachment_id: string; detail?: string; filename?: string; preview_url?: string }[] | null;
  artifacts?: ChatArtifact[] | null;
  steps?: Record<string, unknown>[] | null;
  trace_id?: string | null;
  created_at: string;
}

export interface AgentChatSessionSummary {
  id: string;
  agent_id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface ChatSessionDetail extends AgentChatSessionSummary {
  messages: AgentChatSessionMessage[];
  has_more?: boolean;
}

export interface PendingToolCall {
  slug: string;
  name: string;
  description?: string | null;
  params: Record<string, unknown>;
}

export interface ToolInvocationLog {
  id: string;
  tool_slug: string;
  tool_id?: string | null;
  source: string;
  status: string;
  params: Record<string, unknown>;
  output?: Record<string, unknown> | null;
  error_message?: string | null;
  latency_ms: number;
  invoke_source: string;
  created_at: string;
}

/** 对话附图（服务端读 attachment，非签名 URL） */

export interface ChatMediaIn {
  attachment_id: string;
  detail?: "auto" | "low" | "high";
}

/** 工具生图/生视频产出；预览用 fetchAttachmentPreviewUrl，非 OSS 签名链接 */

export interface ChatArtifact {
  kind: string; // image | video
  attachment_id?: string | null;
  mime_type?: string | null;
  caption?: string | null;
  status?: "pending" | "running" | "success" | "failed" | "cancelled" | null;
  job_id?: string | null;
  media_asset_id?: string | null;
  progress_percent?: number | null;
  progress_message?: string | null;
  error_message?: string | null;
}

export interface ChatResponse {
  answer: string;
  sources: Record<string, unknown>[];
  steps: Record<string, unknown>[];
  artifacts?: ChatArtifact[];
  pending_tool?: PendingToolCall | null;
  generative_jobs?: { id: string; kind: string; status: string }[];
}

/** chatAgent 返回值：业务数据 + 响应头/信封中的 trace_id。 */

export interface ChatAgentResult extends ChatResponse {
  trace_id?: string;
}

export interface AgentDebugToken {
  access_token: string;
  token_type: string;
  expires_in: number;
  expires_at: string;
  agent_id: string;
  purpose: string;
  warning: string;
}

export interface AgentApiKey {
  id: string;
  name: string;
  key_prefix: string;
  status: "active" | "revoked";
  created_at: string;
  last_used_at?: string | null;
  revoked_at?: string | null;
}

export interface AgentApiKeyCreated extends AgentApiKey {
  secret: string;
  warning: string;
}
