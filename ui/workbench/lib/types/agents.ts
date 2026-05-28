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
  config?: Record<string, unknown>;
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
  attachment_id: string;
  mime_type?: string | null;
  caption?: string | null;
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

