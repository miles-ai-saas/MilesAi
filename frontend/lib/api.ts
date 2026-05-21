import axios, { AxiosInstance } from "axios";
import type {
  Agent,
  AlertConfig,
  ApiResponse,
  AppCategory,
  AppInstall,
  AppInstallResult,
  ChatResponse,
  CustomTool,
  Document,
  Flow,
  FlowGraph,
  FlowVersion,
  HookDefinition,
  InterceptLog,
  KnowledgeBase,
  MarketplaceApp,
  ModelConfig,
  MonitorReport,
  MonitorStats,
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

  listAuditLogs: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<TenantAuditLog>(`/audit/logs?${buildPageQuery(page, size)}`),

  listSensitiveWords: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<SensitiveWord>(`/compliance/words?${buildPageQuery(page, size)}`),
  createSensitiveWord: (word: string, action: "warn" | "block", category?: string) =>
    post<SensitiveWord>("/compliance/words", { word, action, category }),
  deleteSensitiveWord: (wordId: string) =>
    http.delete(`/compliance/words/${wordId}`).then(() => undefined),
  listInterceptLogs: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<InterceptLog>(`/compliance/logs?${buildPageQuery(page, size)}`),

  listPromptTemplates: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<PromptTemplate>(`/prompt-templates?${buildPageQuery(page, size)}`),
  createPromptTemplate: (name: string, content: string, description?: string) =>
    post<PromptTemplate>("/prompt-templates", { name, content, description }),
  deletePromptTemplate: (id: string) =>
    http.delete(`/prompt-templates/${id}`).then(() => undefined),

  listModelConfigs: () => get<ModelConfig[]>("/models"),
  createModelConfig: (payload: {
    name: string;
    provider: string;
    model_name: string;
    api_base?: string;
    api_key?: string;
  }) => post<ModelConfig>("/models", payload),

  listFlows: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<Flow>(`/flows?${buildPageQuery(page, size)}`),
  createFlow: (name: string, graph_json?: FlowGraph) =>
    post<Flow>("/flows", { name, graph_json: graph_json || { nodes: [], edges: [] } }),
  getFlowGraph: (flowId: string) => get<FlowVersion>(`/flows/${flowId}/graph`),
  saveFlowGraph: (flowId: string, graph_json: FlowGraph, remark?: string) =>
    put<FlowVersion>(`/flows/${flowId}/graph`, { graph_json, remark }),
  publishFlow: (flowId: string) => post<Flow>(`/flows/${flowId}/publish`),
  runFlow: (flowId: string, inputs: Record<string, string>) =>
    post<{ output: unknown; steps: unknown[] }>(`/flows/${flowId}/run`, { inputs }),

  listKbs: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<KnowledgeBase>(`/kb?${buildPageQuery(page, size)}`),
  createKb: (name: string, description?: string) =>
    post<KnowledgeBase>("/kb", { name, description: description || "" }),

  listAgents: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<Agent>(`/agents?${buildPageQuery(page, size)}`),
  createAgent: (payload: {
    name: string;
    kb_ids?: string[];
    published_flow_id?: string;
    system_prompt?: string;
    prompt_template_id?: string;
    model_config_id?: string;
  }) => post<Agent>("/agents", { kb_ids: [], ...payload }),
  chatAgent: (agentId: string, query: string) =>
    post<ChatResponse>(`/agents/${agentId}/chat`, { query }),

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
  }) => post<HookDefinition>("/hooks", payload),

  listCustomTools: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<CustomTool>(`/tools?${buildPageQuery(page, size)}`),
  createCustomTool: (name: string, description: string, config: Record<string, unknown>) =>
    post<CustomTool>("/tools", { name, description, tool_type: "http", config }),
  listBuiltinTools: () => get<Record<string, string>[]>("/tools/builtin"),

  listSkillPackages: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<SkillPackage>(`/skill-packages?${buildPageQuery(page, size)}`),
  createSkillPackage: (payload: {
    name: string;
    description?: string;
    tool_names?: string[];
    prompt_snippet?: string;
  }) => post<SkillPackage>("/skill-packages", payload),
  deleteSkillPackage: (id: string) =>
    http.delete(`/skill-packages/${id}`).then(() => undefined),

  listMcpServices: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<McpService>(`/mcp?${buildPageQuery(page, size)}`),
  createMcpService: (name: string, endpoint_url: string) =>
    post<McpService>("/mcp", { name, endpoint_url }),
  syncMcpService: (serviceId: string) =>
    post<{ tools: Record<string, unknown>[]; synced_at: string }>(`/mcp/${serviceId}/sync`),

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
  listMarketplaceApps: (page = 1, size = DEFAULT_PAGE_SIZE, category?: string) =>
    getPage<MarketplaceApp>(
      `/marketplace/apps?${buildPageQuery(page, size)}${category ? `&category=${category}` : ""}`
    ),
  getMarketplaceApp: (appId: string) => get<MarketplaceApp & { manifest: Record<string, unknown> }>(
    `/marketplace/apps/${appId}`
  ),
  installMarketplaceApp: (appId: string) =>
    post<AppInstallResult>(`/marketplace/apps/${appId}/install`),
  listAppInstalls: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<AppInstall>(`/marketplace/installs?${buildPageQuery(page, size)}`),
};
