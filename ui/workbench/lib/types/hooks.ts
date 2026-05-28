/** 域类型：与 backend OpenAPI 对齐。 */

import type { EnumOption } from "@/lib/enum-meta";
export interface HookDefinition {
  id: string;
  name: string;
  hook_type: string;
  config: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
}

export interface HookBinding {
  id: string;
  hook_id: string;
  scope: string;
  target_id?: string | null;
  trigger: string;
  priority: number;
  is_active: boolean;
  created_at: string;
}

/**
 * 各域 GET …/meta 响应类型（与 backend tenant 下 schemas/meta.py 一致）。
 * 文案源：tenant 各模块 meta.py；前端消费见 lib/enum-meta.ts 链路说明。
 */

/** GET /hooks/meta */

export interface HookExecutionLog {
  id: string;
  hook_id: string;
  binding_id?: string | null;
  event_id: string;
  trace_id?: string | null;
  trigger: string;
  scope: string;
  target_id?: string | null;
  status: string;
  http_status?: number | null;
  duration_ms?: number | null;
  response_action?: string | null;
  error_message?: string | null;
  created_at: string;
}
