/** 域类型：与 backend OpenAPI 对齐。 */

import type { EnumOption } from "@/lib/enum-meta";
import type { TagRef } from "./tags";
export interface HookMeta {
  triggers: EnumOption[];
  scopes: EnumOption[];
  on_failure_options: EnumOption[];
  response_actions: EnumOption[];
  schema_version: string;
}

/** GET /compliance/meta */

export interface ComplianceMeta {
  sensitive_actions: EnumOption[];
  scan_modules: EnumOption[];
}

/** GET /flows/meta */

export interface FlowMeta {
  statuses: EnumOption[];
}

/** GET /flows/templates — 内置画布模板 */

export interface KbMeta {
  retrieval_modes: EnumOption[];
  search_modes: EnumOption[];
  search_sources: EnumOption[];
  document_statuses: EnumOption[];
  media_types: EnumOption[];
}

/** GET /tools/meta */

export interface ToolsMeta {
  tool_types: EnumOption[];
  catalog_sources: EnumOption[];
  invocation_statuses: EnumOption[];
}

/** GET /agents/meta */

export interface AgentMeta {
  statuses: EnumOption[];
  agent_types: EnumOption[];
  sub_agent_role_hints: EnumOption[];
  primary_paths: EnumOption[];
  runtime_modes: EnumOption[];
  planners: EnumOption[];
  schema_version: string;
}

/** GET /prompt-templates/meta */

export interface PromptMeta {
  active_states: EnumOption[];
  schema_version: string;
}

/** GET /marketplace/meta */

export interface MarketplaceMeta {
  app_statuses: EnumOption[];
  catalog_sorts: EnumOption[];
  visibilities?: EnumOption[];
  review_mode?: "platform" | "tenant" | "off";
  schema_version: string;
}

/** GET /mcp/meta */

export interface McpMeta {
  statuses: EnumOption[];
  transport_filters: EnumOption[];
  transport_types: EnumOption[];
  sync_displays: EnumOption[];
  schema_version: string;
}

/** GET /attachments/meta */

export interface AttachmentMeta {
  purposes: EnumOption[];
  purpose_filters: EnumOption[];
  schema_version: string;
}

/** GET /skill-packages/meta */

export interface SkillMeta {
  source_types: EnumOption[];
  active_states: EnumOption[];
  schema_version: string;
}

/** GET /a2a/peers/meta */

export interface A2aMeta {
  peer_statuses: EnumOption[];
  invoke_policies: EnumOption[];
  peer_role_hints: EnumOption[];
  schema_version: string;
}

/** GET /monitor/meta */

export interface MonitorMeta {
  health_components: EnumOption[];
  overall_health_statuses: EnumOption[];
  trend_day_ranges: EnumOption[];
  schema_version: string;
}

/** GET /tasks/meta */

export interface TaskMeta {
  statuses: EnumOption[];
  status_filters: EnumOption[];
  schema_version: string;
}

/** GET /categories/meta */

export interface CategoryMeta {
  domains: EnumOption[];
  schema_version: string;
}

/** GET /tags/meta */

export interface TagMeta {
  entity_types: EnumOption[];
  schema_version: string;
}

/** GET /audit/meta */

export interface AuditMeta {
  resource_types: EnumOption[];
  resource_type_filters: EnumOption[];
  action_filters: EnumOption[];
  action_labels: EnumOption[];
  schema_version: string;
}
