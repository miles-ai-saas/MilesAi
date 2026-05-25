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

export interface A2aPeerRefInput {
  peer_id: string;
  role_hint?: string | null;
  trigger_keywords?: string[];
  enabled?: boolean;
}

export interface A2aPeerRef {
  id: string;
  name: string;
  role_hint?: string | null;
  trigger_keywords: string[];
  enabled: boolean;
  status: string;
  card_display_name?: string | null;
  agent_card_url?: string | null;
}

export type AgentType = "custom" | "a2a";

export type CategoryDomain = "agent" | "prompt" | "skill" | "tool";

export interface SysCategory {
  id: string;
  domain: CategoryDomain;
  parent_id?: string | null;
  name: string;
  slug: string;
  sort_order: number;
  is_system: boolean;
  created_at: string;
}

export interface TagRef {
  id: string;
  name: string;
  slug: string;
}

export interface TenantTag {
  id: string;
  tenant_id: string;
  name: string;
  slug: string;
  created_at: string;
}

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

export interface PromptTemplate {
  id: string;
  category_id?: string | null;
  category_name?: string | null;
  tags?: TagRef[];
  name: string;
  description?: string | null;
  content: string;
  is_active: boolean;
  created_at: string;
}

export type ModelSource = "builtin" | "custom";
export type ModelCredentialStatus = "platform" | "tenant" | "missing";

export interface ModelConfig {
  id: string;
  source: ModelSource;
  name: string;
  vendor: string;
  provider: string;
  model_name: string;
  model_code?: string | null;
  model_type: string;
  description?: string | null;
  context_window?: string | null;
  badge?: string | null;
  api_base?: string | null;
  is_active: boolean;
  publish_status?: string | null;
  credential_status: ModelCredentialStatus;
  has_api_key: boolean;
  extra?: { embedding_dimension?: number; invoke_mode?: string; litellm_model?: string };
  created_at: string;
}

export interface ModelCatalogMeta {
  vendors: { value: string; label: string }[];
  model_types: { value: string; label: string }[];
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

export interface ToolParameterSpec {
  name: string;
  type: "string" | "number" | "integer" | "boolean";
  description?: string | null;
  required?: boolean;
  default?: unknown;
  enum?: string[];
}

export interface ToolCatalogItem {
  source: "builtin" | "custom" | string;
  slug: string;
  name: string;
  description?: string | null;
  category_id?: string | null;
  category_name?: string | null;
  parameters?: ToolParameterSpec[];
  version?: string | null;
  require_confirmation?: boolean;
  tool_id?: string | null;
  tool_type?: string | null;
  updated_at?: string | null;
}

export interface CustomTool {
  id: string;
  slug: string;
  name: string;
  description?: string | null;
  tool_type: string;
  category_id?: string | null;
  category_name?: string | null;
  tags?: TagRef[];
  version: string;
  require_confirmation: boolean;
  parameters: ToolParameterSpec[];
  config: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ToolCreatePayload {
  slug: string;
  name: string;
  description?: string | null;
  tool_type?: "http" | "script";
  category_id?: string | null;
  tag_ids?: string[];
  version?: string;
  require_confirmation?: boolean;
  parameters?: ToolParameterSpec[];
  config: Record<string, unknown>;
}

/** 技能包元数据；正文在服务端磁盘 SKILL.md（slug 为目录名）。 */
export interface SkillPackage {
  id: string;
  tenant_id?: string;
  category_id?: string | null;
  category_name?: string | null;
  tags?: TagRef[];
  slug: string;
  name: string;
  description?: string | null;
  source_type: string;
  tool_names: string[];
  prompt_snippet?: string | null;
  config: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SkillFileNode {
  name: string;
  path: string;
  type: "file" | "dir";
  children?: SkillFileNode[];
}

export interface SkillImportResult {
  imported: number;
  skipped: number;
  errors: string[];
}

export interface KnowledgeBase {
  id: string;
  tenant_id?: string;
  name: string;
  description?: string | null;
  is_public?: boolean;
  embedding_model_config_id: string;
  embedding_model_name?: string | null;
  embedding_dimension: number;
  chunk_size?: number;
  chunk_overlap?: number;
  retrieval_mode?: "vector" | "hybrid";
  hybrid_alpha?: number;
  rerank_model_config_id?: string | null;
  rerank_model_name?: string | null;
  rerank_candidate_k?: number;
  created_at?: string;
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

export interface ChatResponse {
  answer: string;
  sources: Record<string, unknown>[];
  steps: Record<string, unknown>[];
  pending_tool?: PendingToolCall | null;
}

/** chatAgent 返回值：业务数据 + 响应头/信封中的 trace_id。 */
export interface ChatAgentResult extends ChatResponse {
  trace_id?: string;
}

export interface Document {
  id: string;
  kb_id: string;
  filename: string;
  mime_type: string;
  file_size: number;
  status: string;
  fail_reason?: string | null;
  chunk_count?: number | null;
  created_at: string;
}

export interface DocumentChunk {
  id: string;
  document_id: string;
  kb_id: string;
  chunk_index: number;
  content: string;
  page_no?: number | null;
  created_at: string;
}

export interface KbQuota {
  used_knowledge_bases: number;
  max_knowledge_bases: number;
  used_storage_mb: number;
  max_storage_mb: number;
  max_file_mb: number;
}

export interface KbSearchLog {
  id: string;
  tenant_id: string;
  kb_id: string | null;
  kb_ids: string[] | null;
  query: string;
  top_k: number;
  hit_count: number;
  latency_ms: number;
  retrieval_mode: string;
  source: string;
  actor_user_id: string | null;
  agent_id: string | null;
  created_at: string;
}

export interface Attachment {
  id: string;
  tenant_id: string;
  uploaded_by: string;
  filename: string;
  mime_type: string;
  file_size: number;
  object_bucket: string;
  purpose: string;
  resource_type: string | null;
  resource_id: string | null;
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

export interface WorkbenchOverview {
  agents: number;
  kbs: number;
  flows: number;
  prompts: number;
  models: number;
  tasks: number;
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

export interface A2aPeer {
  id: string;
  name: string;
  description?: string | null;
  base_url?: string | null;
  agent_card_url: string;
  card_display_name?: string | null;
  status: string;
  skills_count: number;
  last_synced_at?: string | null;
  last_error?: string | null;
  created_at: string;
}

export interface A2aPeerProbeResult {
  ok: boolean;
  card_url: string;
  card_display_name?: string | null;
  skills_count: number;
  message: string;
}

export interface A2aPeerSyncResult {
  peer: A2aPeer;
  card_url: string;
  message: string;
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
  rating_avg: number;
  rating_count: number;
  category_id?: string | null;
  category_name?: string | null;
  installed: boolean;
  review_note?: string | null;
  submitted_at?: string | null;
  reviewed_at?: string | null;
  created_at: string;
}

export interface AppRating {
  id: string;
  app_id: string;
  user_id: string;
  score: number;
  comment?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MarketplaceAppDetail extends MarketplaceApp {
  manifest: Record<string, unknown>;
  my_rating?: AppRating | null;
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
