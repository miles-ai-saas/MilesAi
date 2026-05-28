/** 域类型：与 backend OpenAPI 对齐。 */

import type { EnumOption } from "@/lib/enum-meta";
export interface GenerativeJobOut {
  id: string;
  tenant_id: string;
  kind: string;
  status: "pending" | "running" | "success" | "failed" | "cancelled";
  source: string;
  progress_message?: string | null;
  progress_percent?: number | null;
  params: Record<string, unknown>;
  result?: Record<string, unknown> | null;
  error_message?: string | null;
  celery_task_id?: string | null;
  celery_task_record_id?: string | null;
  created_at: string;
  updated_at: string;
}
