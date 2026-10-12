/** 域类型：与 backend OpenAPI 对齐。 */

import type { EnumOption } from "@/lib/enum-meta";
export interface TaskTrendPoint {
  date: string;
  pending: number;
  running: number;
  success: number;
  failed: number;
  cancelled: number;
  total: number;
}

export interface MonitorTrends {
  task_by_day: TaskTrendPoint[];
  intercept_by_day: { date: string; count: number }[];
}

export interface MonitorStats {
  knowledge_bases: number;
  documents: number;
  agents: number;
  flows: number;
  intercept_logs_today: number;
  pending_documents: number;
}

export interface TaskSummary {
  pending: number;
  running: number;
  success: number;
  failed: number;
  cancelled: number;
  total: number;
}

export interface MonitorReport {
  stats: MonitorStats;
  tasks: TaskSummary;
  documents_by_status: Record<string, number>;
  marketplace_installs: number;
}

export interface TaskRecord {
  id: string;
  celery_task_id: string;
  task_name: string;
  status: string;
  resource_type?: string | null;
  resource_id?: string | null;
  fail_reason?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AlertConfig {
  enabled: boolean;
  webhook_url: string;
  email_notify_to: string;
  notify_on_task_failed: boolean;
  notify_on_health_degraded: boolean;
  notify_on_tokens_monthly_threshold: boolean;
  tokens_monthly_warn_percent: number;
}

export interface ModelUsageRow {
  model_config_id?: string | null;
  model_name: string;
  call_count: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface ModelUsageReport {
  days: number;
  rows: ModelUsageRow[];
  total_tokens: number;
}

export interface AgentSlaMetrics {
  call_count: number;
  success_count: number;
  failed_count: number;
  blocked_count: number;
  success_rate: number;
  latency_avg_ms: number;
  latency_p50_ms: number;
  latency_p95_ms: number;
  tokens_per_call_avg: number;
  total_tokens: number;
}

export interface AgentSlaRouteRow extends AgentSlaMetrics {
  route: string;
}

export interface AgentSlaAgentRow extends AgentSlaMetrics {
  agent_id: string;
  agent_name?: string | null;
}

export interface AgentSlaDailyPoint {
  date: string;
  call_count: number;
  success_rate: number;
  latency_avg_ms: number;
}

export interface AgentSlaReport {
  days: number;
  agent_id?: string | null;
  overview: AgentSlaMetrics;
  by_route: AgentSlaRouteRow[];
  by_agent: AgentSlaAgentRow[];
  by_day: AgentSlaDailyPoint[];
}
