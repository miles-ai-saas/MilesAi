export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T | null;
  trace_id?: string;
}

export interface PageResult<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserInfo {
  id: string;
  username: string;
  email: string;
  tenant_id: string;
  is_superuser: boolean;
  permissions: string[];
}

export interface TenantUser {
  id: string;
  username: string;
  email: string;
  phone?: string | null;
  tenant_id: string;
  is_active: boolean;
  is_superuser: boolean;
  role_codes: string[];
}

export interface Permission {
  id: string;
  code: string;
  name: string;
  module: string;
  description?: string | null;
}

export interface PermissionGroup {
  module: string;
  permissions: Permission[];
}

export interface Role {
  id: string;
  tenant_id?: string | null;
  name: string;
  code: string;
  description?: string | null;
  is_system: boolean;
  permission_codes: string[];
}

export interface ConfigDefinition {
  key: string;
  label: string;
  category: string;
  description: string;
  value_type: string;
  default_value: unknown;
}

export interface RuntimeInfo {
  components: Record<string, string>;
  settings_preview: Record<string, string | number | boolean | null>;
}

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

export interface TenantAuditLog {
  id: string;
  tenant_id: string;
  user_id?: string | null;
  action: string;
  resource_type?: string | null;
  resource_id?: string | null;
  ip_address?: string | null;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface Flow {
  id: string;
  tenant_id: string;
  name: string;
  description?: string | null;
  status: "draft" | "published";
  current_version: number;
  created_at: string;
}

export interface FlowVersion {
  id: string;
  flow_id: string;
  version: number;
  graph_json: FlowGraph;
  remark?: string | null;
}

export interface FlowGraph {
  nodes: FlowNode[];
  edges: FlowEdge[];
}

export interface FlowNode {
  id: string;
  type: string;
  position?: { x: number; y: number };
  data: Record<string, unknown>;
}

export interface FlowEdge {
  id?: string;
  source: string;
  target: string;
  sourceHandle?: string;
  targetHandle?: string;
}

export interface Agent {
  id: string;
  name: string;
  description?: string | null;
  status: string;
  kb_ids: string[];
  published_flow_id?: string | null;
  model_config_id?: string | null;
  prompt_template_id?: string | null;
  system_prompt?: string | null;
}

export interface PromptTemplate {
  id: string;
  name: string;
  description?: string | null;
  content: string;
  is_active: boolean;
  created_at: string;
}

export interface ModelConfig {
  id: string;
  name: string;
  provider: string;
  model_name: string;
  api_base?: string | null;
  is_active: boolean;
  created_at: string;
}

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

export interface CustomTool {
  id: string;
  name: string;
  description?: string | null;
  tool_type: string;
  config: Record<string, unknown>;
  is_active: boolean;
}

export interface SkillPackage {
  id: string;
  name: string;
  description?: string | null;
  tool_names: string[];
  prompt_snippet?: string | null;
  config: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
}

export interface KnowledgeBase {
  id: string;
  name: string;
  description?: string | null;
}

export interface ChatResponse {
  answer: string;
  sources: Record<string, unknown>[];
  steps: Record<string, unknown>[];
}

export interface Document {
  id: string;
  kb_id: string;
  filename: string;
  mime_type: string;
  file_size: number;
  status: string;
  fail_reason?: string | null;
  created_at: string;
}

export interface SensitiveWord {
  id: string;
  word: string;
  category?: string | null;
  action: "warn" | "block";
  is_active: boolean;
}

export interface InterceptLog {
  id: string;
  module: string;
  direction: string;
  matched_word?: string | null;
  action: string;
  content_snippet?: string | null;
  created_at: string;
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

export interface McpService {
  id: string;
  name: string;
  endpoint_url: string;
  status: string;
  tools_cache: Record<string, unknown>[];
  last_sync_at?: string | null;
}

export interface AppCategory {
  id: string;
  name: string;
  slug: string;
  sort_order: number;
}

export interface MarketplaceApp {
  id: string;
  name: string;
  description?: string | null;
  icon?: string | null;
  version: string;
  status: string;
  is_official: boolean;
  install_count: number;
  category_id?: string | null;
  category_name?: string | null;
  installed: boolean;
  created_at: string;
}

export interface AppInstallResult {
  install: {
    id: string;
    app_id: string;
    app_name: string;
    flow_id?: string | null;
    agent_id?: string | null;
    kb_id?: string | null;
  };
  flow_id?: string | null;
  agent_id?: string | null;
  kb_id?: string | null;
  message: string;
}

export interface AppInstall {
  id: string;
  app_id: string;
  app_name: string;
  flow_id?: string | null;
  agent_id?: string | null;
  kb_id?: string | null;
  created_at: string;
}
