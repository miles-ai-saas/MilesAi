/** 域类型：与 backend OpenAPI 对齐。 */

import type { EnumOption } from "@/lib/enum-meta";
export interface McpService {
  id: string;
  name: string;
  endpoint_url: string;
  transport?: string;
  description?: string | null;
  connection_config?: Record<string, unknown>;
  sync_error?: string | null;
  status: string;
  tools_cache: Record<string, unknown>[];
  last_sync_at?: string | null;
  updated_at?: string;
  created_at?: string;
}

