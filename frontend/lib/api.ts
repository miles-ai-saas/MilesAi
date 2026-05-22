import axios, { AxiosInstance } from "axios";
import type {
  Agent,
  AlertConfig,
  ApiResponse,
  AppCategory,
  AppInstall,
  AppInstallResult,
  AppRating,
  ChatResponse,
  ConfigDefinition,
  CustomTool,
  Document,
  Flow,
  FlowGraph,
  FlowVersion,
  HookBinding,
  HookDefinition,
  InterceptLog,
  KnowledgeBase,
  MarketplaceApp,
  MarketplaceAppDetail,
  ModelConfig,
  MonitorReport,
  MonitorStats,
  MonitorTrends,
  PermissionGroup,
  Role,
  RuntimeInfo,
  McpService,
  PageResult,
  PromptTemplate,
  SensitiveWord,
  SkillPackage,
  TaskRecord,
  TokenPair,
  UserInfo,
  TenantUser,
  TenantAuditLog,
} from "./types";
import { getAccessToken, useAuthStore } from "./auth-store";
import { buildPageQuery, DEFAULT_PAGE_SIZE, normalizePageResult } from "./pagination";

const baseURL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function createClient(): AxiosInstance {
  const client = axios.create({ baseURL, timeout: 120000 });
  client.interceptors.request.use((config) => {
    const token = getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });
  client.interceptors.response.use(
    (res) => res,
    (err) => {
      if (err.response?.status === 401 && typeof window !== "undefined") {
        const hadToken = !!getAccessToken();
        if (hadToken) {
          useAuthStore.getState().logout();
          window.location.href = "/login";
        }
      }
      return Promise.reject(err);
    }
  );
  return client;
}

const http = createClient();

function unwrap<T>(body: ApiResponse<T>): T {
  if (body.code !== 0 || body.data === null) {
    throw new Error(body.message || "请求失败");
  }
  return body.data;
}

async function get<T>(url: string): Promise<T> {
  const res = await http.get<ApiResponse<T>>(url);
  return unwrap(res.data);
}

async function getPage<T>(url: string): Promise<PageResult<T>> {
  const raw = await get<PageResult<T> | T[]>(url);
  return normalizePageResult<T>(raw);
}

async function post<T>(url: string, data?: unknown): Promise<T> {
  const res = await http.post<ApiResponse<T>>(url, data);
  return unwrap(res.data);
}

async function put<T>(url: string, data?: unknown): Promise<T> {
  const res = await http.put<ApiResponse<T>>(url, data);
  return unwrap(res.data);
}

async function patch<T>(url: string, data?: unknown): Promise<T> {
  const res = await http.patch<ApiResponse<T>>(url, data);
  return unwrap(res.data);
}

export const api = {
  login: async (username: string, password: string) => {
    const data = await post<TokenPair>("/auth/login", { username, password });
    useAuthStore.getState().setToken(data.access_token);
    const user = await get<UserInfo>("/auth/me");
    useAuthStore.getState().setUser(user);
    return { ...data, user };
  },

  fetchMe: () => get<UserInfo>("/auth/me"),

  logout: () => useAuthStore.getState().logout(),

  listUsers: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<TenantUser>(`/users?${buildPageQuery(page, size)}`),
  createUser: (payload: {
    username: string;
    email: string;
    password: string;
    phone?: string;
    role_ids?: string[];
  }) => post<TenantUser>("/users", payload),
  updateUser: (
    userId: string,
    payload: { email?: string; phone?: string; is_active?: boolean; role_ids?: string[] },
  ) => patch<TenantUser>(`/users/${userId}`, payload),
  deactivateUser: (userId: string) =>
    http.delete<ApiResponse<TenantUser>>(`/users/${userId}`).then((res) => unwrap(res.data)),

  listPermissionGroups: () => get<PermissionGroup[]>("/roles/permissions"),
  listAssignableRoles: () => get<Role[]>("/roles/assignable"),
  listRoles: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<Role>(`/roles?${buildPageQuery(page, size)}`),
  createRole: (payload: {
    name: string;
    code: string;
    description?: string;
    permission_ids: string[];
  }) => post<Role>("/roles", payload),
  updateRole: (
    roleId: string,
    payload: { name?: string; description?: string; permission_ids?: string[] },
  ) => patch<Role>(`/roles/${roleId}`, payload),
  deleteRole: (roleId: string) => http.delete(`/roles/${roleId}`).then(() => undefined),

  listConfigDefinitions: () => get<ConfigDefinition[]>("/system/configs/definitions"),
  getRuntimeInfo: () => get<RuntimeInfo>("/system/configs/runtime"),
  upsertSystemConfig: (key: string, value: unknown, description?: string) =>
    put<{ key: string; value: Record<string, unknown> }>(`/system/configs/${encodeURIComponent(key)}`, {
      value: typeof value === "object" && value !== null ? value : { value },
      description,
    }),

  getMonitorTrends: (days = 7) => get<MonitorTrends>(`/monitor/trends?days=${days}`),

  listAuditLogs: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<TenantAuditLog>(`/audit/logs?${buildPageQuery(page, size)}`),

  listSensitiveWords: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<SensitiveWord>(`/compliance/words?${buildPageQuery(page, size)}`),
  createSensitiveWord: (word: string, action: "warn" | "block", category?: string) =>
    post<SensitiveWord>("/compliance/words", { word, action, category }),
  batchCreateSensitiveWords: (
    words: { word: string; action: "warn" | "block"; category?: string }[],
  ) => post<SensitiveWord[]>("/compliance/words/batch", { words }),
  updateSensitiveWord: (
    wordId: string,
    payload: { action?: "warn" | "block"; category?: string; is_active?: boolean },
  ) => patch<SensitiveWord>(`/compliance/words/${wordId}`, payload),
  deleteSensitiveWord: (wordId: string) =>
    http.delete(`/compliance/words/${wordId}`).then(() => undefined),
  scanCompliance: (text: string, module = "manual_test") =>
    post<{ blocked: boolean; warned: boolean; matches: { word: string; action: string }[] }>(
      "/compliance/scan",
      { text, module },
    ),
  listInterceptLogs: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<InterceptLog>(`/compliance/logs?${buildPageQuery(page, size)}`),

  listPromptTemplates: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<PromptTemplate>(`/prompt-templates?${buildPageQuery(page, size)}`),
  createPromptTemplate: (name: string, content: string, description?: string) =>
    post<PromptTemplate>("/prompt-templates", { name, content, description }),
  updatePromptTemplate: (
    id: string,
    payload: { name?: string; content?: string; description?: string; is_active?: boolean },
  ) => patch<PromptTemplate>(`/prompt-templates/${id}`, payload),
  deletePromptTemplate: (id: string) =>
    http.delete(`/prompt-templates/${id}`).then(() => undefined),

  getModelCatalogMeta: () => get<import("@/lib/types").ModelCatalogMeta>("/models/meta"),
  listModelConfigs: (params?: {
    vendor?: string;
    model_type?: string;
    source?: "builtin" | "custom";
    q?: string;
  }) => {
    const q = new URLSearchParams();
    if (params?.vendor) q.set("vendor", params.vendor);
    if (params?.model_type) q.set("model_type", params.model_type);
    if (params?.source) q.set("source", params.source);
    if (params?.q) q.set("q", params.q);
    const qs = q.toString();
    return get<ModelConfig[]>(`/models${qs ? `?${qs}` : ""}`);
  },
  createModelConfig: (payload: {
    name: string;
    vendor?: string;
    provider?: string;
    model_name: string;
    model_code?: string;
    model_type?: string;
    description?: string;
    api_base?: string;
    api_key?: string;
  }) => post<ModelConfig>("/models", payload),
  updateModelConfig: (
    id: string,
    payload: {
      name?: string;
      vendor?: string;
      provider?: string;
      model_name?: string;
      model_code?: string;
      model_type?: string;
      description?: string;
      api_base?: string;
      api_key?: string;
      is_active?: boolean;
    },
  ) => patch<ModelConfig>(`/models/${id}`, payload),
  upsertBuiltinModelCredentials: (
    id: string,
    payload: { api_key: string; api_base?: string },
  ) => put<ModelConfig>(`/models/builtin/${id}/credentials`, payload),
  deleteBuiltinModelCredentials: async (id: string) => {
    const res = await http.delete<ApiResponse<ModelConfig>>(`/models/builtin/${id}/credentials`);
    return unwrap(res.data);
  },
  deleteModelConfig: (id: string) =>
    http.delete(`/models/${id}`).then(() => undefined),

  listFlows: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<Flow>(`/flows?${buildPageQuery(page, size)}`),
  createFlow: (name: string, graph_json?: FlowGraph) =>
    post<Flow>("/flows", { name, graph_json: graph_json || { nodes: [], edges: [] } }),
  getFlowGraph: (flowId: string) => get<FlowVersion>(`/flows/${flowId}/graph`),
  saveFlowGraph: (flowId: string, graph_json: FlowGraph, remark?: string) =>
    put<FlowVersion>(`/flows/${flowId}/graph`, { graph_json, remark }),
  publishFlow: (flowId: string) => post<Flow>(`/flows/${flowId}/publish`),
  compileFlow: (flowId: string) =>
    post<{
      compilable: boolean;
      engine: string;
      node_order: string[];
      node_types: string[];
      execution_layers: string[][];
      parallel_groups: string[][];
      conditional_nodes: string[];
      errors: string[];
    }>(`/flows/${flowId}/compile`),
  runFlow: (
    flowId: string,
    inputs: Record<string, string>,
    opts?: { useLanggraph?: boolean },
  ) =>
    post<{ output: unknown; steps: unknown[] }>(`/flows/${flowId}/run`, {
      inputs,
      ...(opts?.useLanggraph ? { use_langgraph: true } : {}),
    }),

  listKbs: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<KnowledgeBase>(`/kb?${buildPageQuery(page, size)}`),
  createKb: (name: string, description?: string) =>
    post<KnowledgeBase>("/kb", { name, description: description || "" }),

  listAgents: (page = 1, size = DEFAULT_PAGE_SIZE, agentType?: import("./types").AgentType) => {
    const q = buildPageQuery(page, size);
    const suffix = agentType ? `${q}&agent_type=${agentType}` : q;
    return getPage<Agent>(`/agents?${suffix}`);
  },

  listA2aPeers: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<import("./types").A2aPeer>(`/a2a/peers?${buildPageQuery(page, size)}`),
  createA2aPeer: (payload: {
    name: string;
    base_url: string;
    description?: string;
    auth_config?: Record<string, unknown>;
  }) => post<import("./types").A2aPeer>("/a2a/peers", payload),
  probeA2aPeer: (baseUrl: string) =>
    post<import("./types").A2aPeerProbeResult>("/a2a/peers/probe", { base_url: baseUrl }),
  syncA2aPeerCard: (peerId: string) =>
    post<import("./types").A2aPeerSyncResult>(`/a2a/peers/${peerId}/sync-card`, {}),
  deleteA2aPeer: (peerId: string) =>
    http.delete(`/a2a/peers/${peerId}`).then(() => undefined),
  getAgent: (agentId: string) => get<Agent>(`/agents/${agentId}`),
  createAgent: (payload: {
    agent_type?: import("./types").AgentType;
    name: string;
    description?: string;
    kb_ids?: string[];
    sub_agents?: import("./types").SubAgentBindingInput[];
    a2a_peers?: import("./types").A2aPeerRefInput[];
    published_flow_id?: string;
    system_prompt?: string;
    prompt_template_id?: string;
    model_config_id?: string;
    config?: Record<string, unknown>;
  }) => post<Agent>("/agents", { kb_ids: [], sub_agents: [], a2a_peers: [], ...payload }),
  updateAgent: (
    agentId: string,
    payload: {
      name?: string;
      description?: string;
      status?: "enabled" | "disabled";
      kb_ids?: string[];
      sub_agents?: import("./types").SubAgentBindingInput[];
      a2a_peers?: import("./types").A2aPeerRefInput[];
      published_flow_id?: string | null;
      system_prompt?: string;
      prompt_template_id?: string | null;
      model_config_id?: string | null;
      config?: Record<string, unknown>;
    },
  ) => patch<Agent>(`/agents/${agentId}`, payload),
  deleteAgent: (agentId: string) =>
    http.delete(`/agents/${agentId}`).then(() => undefined),
  chatAgent: (
    agentId: string,
    query: string,
    opts?: { conversationId?: string },
  ) =>
    post<ChatResponse>(`/agents/${agentId}/chat`, {
      query,
      ...(opts?.conversationId ? { conversation_id: opts.conversationId } : {}),
    }),

  getKb: (kbId: string) => get<KnowledgeBase>(`/kb/${kbId}`),
  listDocuments: (kbId: string, page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<Document>(`/kb/${kbId}/documents?${buildPageQuery(page, size)}`),
  uploadDocument: async (kbId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await http.post<ApiResponse<Document>>(`/kb/${kbId}/documents`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return unwrap(res.data);
  },
  deleteDocument: async (kbId: string, documentId: string) => {
    const res = await http.delete<ApiResponse<null>>(`/kb/${kbId}/documents/${documentId}`);
    return unwrap(res.data);
  },
  retryDocument: (kbId: string, documentId: string) =>
    post<Document>(`/kb/${kbId}/documents/${documentId}/retry`),
  searchKb: (kbId: string, query: string, top_k = 5) =>
    post<{ query: string; hits: { content: string; score: number; filename?: string }[] }>(
      `/kb/${kbId}/search`,
      { query, top_k }
    ),

  listHooks: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<HookDefinition>(`/hooks?${buildPageQuery(page, size)}`),
  createHook: (payload: {
    name: string;
    hook_type?: string;
    config: Record<string, unknown>;
    trigger?: string;
    scope?: string;
    target_id?: string;
    priority?: number;
  }) => post<HookDefinition>("/hooks", payload),
  updateHook: (
    id: string,
    payload: { name?: string; config?: Record<string, unknown>; is_active?: boolean },
  ) => patch<HookDefinition>(`/hooks/${id}`, payload),
  deleteHook: (id: string) => http.delete(`/hooks/${id}`).then(() => undefined),
  listHookBindings: (hookId: string) => get<HookBinding[]>(`/hooks/${hookId}/bindings`),
  createHookBinding: (
    hookId: string,
    payload: { scope?: string; target_id?: string; trigger?: string; priority?: number },
  ) => post<HookBinding>(`/hooks/${hookId}/bindings`, payload),
  deleteHookBinding: (bindingId: string) =>
    http.delete(`/hooks/bindings/${bindingId}`).then(() => undefined),

  listToolCatalog: () =>
    get<
      {
        source: string;
        name: string;
        description?: string | null;
        tool_id?: string | null;
        mcp_service_id?: string | null;
        mcp_service_name?: string | null;
      }[]
    >("/tools/catalog"),
  listCustomTools: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<CustomTool>(`/tools?${buildPageQuery(page, size)}`),
  createCustomTool: (name: string, description: string, config: Record<string, unknown>) =>
    post<CustomTool>("/tools", { name, description, tool_type: "http", config }),
  updateCustomTool: (
    id: string,
    payload: { name?: string; description?: string; config?: Record<string, unknown>; is_active?: boolean },
  ) => patch<CustomTool>(`/tools/${id}`, payload),
  deleteCustomTool: (id: string) => http.delete(`/tools/${id}`).then(() => undefined),
  invokeTool: (name: string, params: Record<string, unknown>, toolId?: string) =>
    post<{ tool: string; source: string; output: Record<string, unknown> }>(
      `/tools/${encodeURIComponent(name)}/invoke`,
      { params, tool_id: toolId || null },
    ),
  listBuiltinTools: () => get<Record<string, string>[]>("/tools/builtin"),

  listSkillPackages: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<SkillPackage>(`/skill-packages?${buildPageQuery(page, size)}`),
  createSkillPackage: (payload: {
    name: string;
    description?: string;
    tool_names?: string[];
    prompt_snippet?: string;
  }) => post<SkillPackage>("/skill-packages", payload),
  updateSkillPackage: (
    id: string,
    payload: {
      name?: string;
      description?: string;
      tool_names?: string[];
      prompt_snippet?: string;
      is_active?: boolean;
    },
  ) => patch<SkillPackage>(`/skill-packages/${id}`, payload),
  deleteSkillPackage: (id: string) =>
    http.delete(`/skill-packages/${id}`).then(() => undefined),

  listMcpServices: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<McpService>(`/mcp?${buildPageQuery(page, size)}`),
  createMcpService: (name: string, endpoint_url: string, transport = "sse") =>
    post<McpService>("/mcp", { name, endpoint_url, transport }),
  deleteMcpService: (id: string) => http.delete(`/mcp/${id}`).then(() => undefined),
  syncMcpService: (serviceId: string) =>
    post<{ tools: Record<string, unknown>[]; synced_at: string }>(`/mcp/${serviceId}/sync`),
  invokeMcpTool: (serviceId: string, toolName: string, params: Record<string, unknown>) =>
    post<{ service_id: string; tool_name: string; output: Record<string, unknown> }>(
      `/mcp/${serviceId}/tools/${encodeURIComponent(toolName)}/invoke`,
      { params },
    ),

  getMonitorStats: () => get<MonitorStats>("/monitor/stats"),
  getMonitorReport: () => get<MonitorReport>("/monitor/report"),
  exportMonitorReport: () =>
    http.get("/monitor/report/export", { responseType: "blob" }).then((res) => res.data as Blob),
  getMonitorHealth: () => get<{ status: string; components: Record<string, unknown> }>("/monitor/health"),
  getAlertConfig: () => get<AlertConfig>("/monitor/alerts"),
  saveAlertConfig: (body: AlertConfig) => put<AlertConfig>("/monitor/alerts", body),
  testAlertConfig: (body: AlertConfig) => post<{ ok: boolean; message?: string; status?: number }>(
    "/monitor/alerts/test",
    body
  ),

  listTasks: (page = 1, size = DEFAULT_PAGE_SIZE, status?: string) =>
    getPage<TaskRecord>(
      `/tasks?${buildPageQuery(page, size)}${status ? `&status=${status}` : ""}`
    ),
  getTask: (taskId: string) => get<TaskRecord>(`/tasks/${taskId}`),
  cancelTask: (taskId: string) => post<TaskRecord>(`/tasks/${taskId}/cancel`),
  retryTask: (taskId: string) => post<TaskRecord>(`/tasks/${taskId}/retry`),

  listMarketplaceCategories: () => get<AppCategory[]>("/marketplace/categories"),
  listMarketplaceApps: (
    page = 1,
    size = DEFAULT_PAGE_SIZE,
    category?: string,
    sort: "installs" | "rating" = "installs",
  ) =>
    getPage<MarketplaceApp>(
      `/marketplace/apps?${buildPageQuery(page, size)}${category ? `&category=${category}` : ""}&sort=${sort}`,
    ),
  listPendingMarketplaceApps: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<MarketplaceApp>(`/marketplace/apps/pending?${buildPageQuery(page, size)}`),
  listMyMarketplaceApps: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<MarketplaceApp>(`/marketplace/apps/mine?${buildPageQuery(page, size)}`),
  getMarketplaceApp: (appId: string) => get<MarketplaceAppDetail>(`/marketplace/apps/${appId}`),
  listMarketplaceAppRatings: (appId: string, page = 1, size = 10) =>
    getPage<AppRating>(`/marketplace/apps/${appId}/ratings?${buildPageQuery(page, size)}`),
  createMarketplaceAppFromResources: (body: {
    name: string;
    description?: string;
    icon?: string;
    category_slug?: string;
    flow_id?: string;
    agent_id?: string;
    kb_id?: string;
  }) => post<MarketplaceApp>("/marketplace/apps/from-resources", body),
  publishMarketplaceApp: (appId: string) =>
    post<MarketplaceApp>(`/marketplace/apps/${appId}/publish`),
  approveMarketplaceApp: (appId: string) =>
    post<MarketplaceApp>(`/marketplace/apps/${appId}/approve`),
  rejectMarketplaceApp: (appId: string, note?: string) =>
    post<MarketplaceApp>(`/marketplace/apps/${appId}/reject`, { note }),
  rateMarketplaceApp: (appId: string, body: { score: number; comment?: string }) =>
    post<AppRating>(`/marketplace/apps/${appId}/ratings`, body),
  deleteMyMarketplaceRating: (appId: string) =>
    http.delete(`/marketplace/apps/${appId}/ratings/mine`).then(() => undefined),
  installMarketplaceApp: (appId: string) =>
    post<AppInstallResult>(`/marketplace/apps/${appId}/install`),
  listAppInstalls: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<AppInstall>(`/marketplace/installs?${buildPageQuery(page, size)}`),
};
