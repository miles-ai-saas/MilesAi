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
  notify_on_task_failed: boolean;
  notify_on_health_degraded: boolean;
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

