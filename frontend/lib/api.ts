/**
 * 租户 API 客户端（链路 §2，索引见 `lib/chains.ts`）。
 * 约定：`ApiResponse` 信封 `code===0` 才成功；分页走 `getPage` + `normalizePageResult`。
 */

import axios, { AxiosInstance } from "axios";
import type {
  Agent,
  AgentArchitecture,
  AgentStats,
  AlertConfig,
  ApiResponse,
  AppCategory,
  AppInstall,
  AppInstallResult,
  AppRating,
  ChatResponse,
  ChatAgentResult,
  ConfigDefinition,
  CustomTool,
  Attachment,
  Document,
  DocumentChunk,
  Flow,
  FlowGraph,
  FlowVersion,
  HookBinding,
  HookDefinition,
  InterceptLog,
  KnowledgeBase,
  KbQuota,
  KbSearchLog,
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
  ComplianceScanBindings,
  ComplianceScanResult,
  LibraryWord,
  WordLibrary,
  SkillPackage,
  TagRef,
  TaskRecord,
  TenantTag,
  TokenPair,
  UserInfo,
  TenantUser,
  TenantAuditLog,
  WorkbenchOverview,
} from "./types";
import { getAccessToken, useAuthStore } from "./auth-store";
import { getApiErrorMessage } from "./api-error";
import { buildPageQuery, DEFAULT_PAGE_SIZE, normalizePageResult } from "./pagination";

export { getApiErrorMessage } from "./api-error";

function appendTagIds(base: string, tagIds?: string[]): string {
  if (!tagIds?.length) return base;
  return tagIds.reduce((s, id) => `${s}&tag_ids=${encodeURIComponent(id)}`, base);
}

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
      return Promise.reject(new Error(getApiErrorMessage(err)));
    }
  );
  return client;
}

const http = createClient();

function unwrap<T>(body: ApiResponse<T>): T {
  if (body.code !== 0) {
    throw new Error(body.message || "请求失败");
  }
  return body.data as T;
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

function readTraceId(headers: Record<string, unknown>, body: ApiResponse<unknown>): string | undefined {
  const fromHeader = headers["x-trace-id"];
  if (typeof fromHeader === "string" && fromHeader.trim()) return fromHeader.trim();
  if (typeof body.trace_id === "string" && body.trace_id.trim()) return body.trace_id.trim();
  return undefined;
}

async function postWithTrace<T extends object>(
  url: string,
  data?: unknown,
): Promise<T & { trace_id?: string }> {
  const res = await http.post<ApiResponse<T>>(url, data);
  const payload = unwrap(res.data);
  const trace_id = readTraceId(res.headers as Record<string, unknown>, res.data);
  return trace_id ? { ...payload, trace_id } : payload;
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
  // --- 鉴权（chains §1）---
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

  listAuditLogs: (
    page = 1,
    size = DEFAULT_PAGE_SIZE,
    filters?: { action?: string; resource_type?: string },
  ) => {
    const q = new URLSearchParams(buildPageQuery(page, size));
    if (filters?.action) q.set("action", filters.action);
    if (filters?.resource_type) q.set("resource_type", filters.resource_type);
    return getPage<TenantAuditLog>(`/audit/logs?${q.toString()}`);
  },

  getComplianceScanBindings: () => get<ComplianceScanBindings>("/compliance/bindings"),
  setComplianceScanBindings: (libraryIds: string[]) =>
    http
      .put("/compliance/bindings", { library_ids: libraryIds })
      .then((r) => r.data.data as ComplianceScanBindings),
  listWordLibraries: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<WordLibrary>(`/compliance/libraries?${buildPageQuery(page, size)}`),
  getWordLibrary: (libraryId: string) => get<WordLibrary>(`/compliance/libraries/${libraryId}`),
  createWordLibrary: (payload: {
    name: string;
    description?: string;
    is_active?: boolean;
    sort_order?: number;
  }) => post<WordLibrary>("/compliance/libraries", payload),
  updateWordLibrary: (
    libraryId: string,
    payload: Partial<{
      name: string;
      description: string | null;
      is_active: boolean;
      sort_order: number;
    }>,
  ) => patch<WordLibrary>(`/compliance/libraries/${libraryId}`, payload),
  deleteWordLibrary: (libraryId: string) =>
    http.delete(`/compliance/libraries/${libraryId}`).then(() => undefined),
  listLibraryWords: (libraryId: string, page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<LibraryWord>(
      `/compliance/libraries/${libraryId}/words?${buildPageQuery(page, size)}`,
    ),
  addLibraryWord: (
    libraryId: string,
    payload: { word: string; action: "warn" | "block"; is_active?: boolean },
  ) => post<LibraryWord>(`/compliance/libraries/${libraryId}/words`, payload),
  batchAddLibraryWords: (
    libraryId: string,
    words: { word: string; action: "warn" | "block"; is_active?: boolean }[],
  ) =>
    post<LibraryWord[]>(`/compliance/libraries/${libraryId}/words/batch`, { words }),
  updateLibraryWord: (
    libraryId: string,
    bindingId: string,
    payload: { action?: "warn" | "block"; is_active?: boolean },
  ) => patch<LibraryWord>(`/compliance/libraries/${libraryId}/words/${bindingId}`, payload),
  deleteLibraryWord: (libraryId: string, bindingId: string) =>
    http
      .delete(`/compliance/libraries/${libraryId}/words/${bindingId}`)
      .then(() => undefined),
  scanCompliance: (text: string, module = "manual_test") =>
    post<ComplianceScanResult>("/compliance/scan", { text, module }),
  listInterceptLogs: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<InterceptLog>(`/compliance/logs?${buildPageQuery(page, size)}`),

  listCategories: async (domain: import("./types").CategoryDomain) => {
    const raw = await get<import("./types").SysCategory[] | null>(
      `/categories?domain=${domain}`,
    );
    return Array.isArray(raw) ? raw : [];
  },
  listTags: () => get<TenantTag[]>("/tags"),
  createTag: (name: string) => post<TenantTag>("/tags", { name }),
  deleteTag: (id: string) => http.delete(`/tags/${id}`).then(() => undefined),

  listPromptTemplates: (
    page = 1,
    size = DEFAULT_PAGE_SIZE,
    categoryId?: string,
    tagIds?: string[],
  ) => {
    let q = buildPageQuery(page, size);
    if (categoryId) q += `&category_id=${categoryId}`;
    q = appendTagIds(q, tagIds);
    return getPage<PromptTemplate>(`/prompt-templates?${q}`);
  },
  createPromptTemplate: (
    name: string,
    content: string,
    description?: string,
    categoryId?: string,
    tagIds?: string[],
  ) =>
    post<PromptTemplate>("/prompt-templates", {
      name,
      content,
      description,
      category_id: categoryId || null,
      tag_ids: tagIds ?? [],
    }),
  updatePromptTemplate: (
    id: string,
    payload: {
      name?: string;
      content?: string;
      description?: string;
      is_active?: boolean;
      category_id?: string | null;
      tag_ids?: string[];
    },
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

  listFlows: (page = 1, size = DEFAULT_PAGE_SIZE, tagIds?: string[]) => {
    let q = buildPageQuery(page, size);
    q = appendTagIds(q, tagIds);
    return getPage<Flow>(`/flows?${q}`);
  },
  createFlow: (payload: {
    name: string;
    description?: string | null;
    tag_ids?: string[];
    graph_json?: FlowGraph;
  }) =>
    post<Flow>("/flows", {
      name: payload.name,
      description: payload.description ?? null,
      tag_ids: payload.tag_ids ?? [],
      graph_json: payload.graph_json ?? { nodes: [], edges: [] },
    }),
  updateFlow: (
    flowId: string,
    payload: { name?: string; description?: string | null; tag_ids?: string[] },
  ) => patch<Flow>(`/flows/${flowId}`, payload),
  getFlow: (flowId: string) => get<Flow>(`/flows/${flowId}`),
  getFlowGraph: (flowId: string) => get<FlowVersion>(`/flows/${flowId}/graph`),
  listFlowVersions: (flowId: string) =>
    get<import("./types").FlowVersionSummary[]>(`/flows/${flowId}/versions`),
  getFlowVersion: (flowId: string, version: number) =>
    get<FlowVersion>(`/flows/${flowId}/versions/${version}`),
  saveFlowGraph: (flowId: string, graph_json: FlowGraph, remark?: string) =>
    put<FlowVersion>(`/flows/${flowId}/graph`, { graph_json, remark }),
  publishFlow: (flowId: string) => post<Flow>(`/flows/${flowId}/publish`),
  deleteFlow: (flowId: string) =>
    http.delete(`/flows/${flowId}`).then(() => undefined),
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
      error_details: { code: string; message: string; node_id?: string | null }[];
    }>(`/flows/${flowId}/compile`),
  runFlow: (
    flowId: string,
    payload: {
      inputs: Record<string, string>;
      kb_ids?: string[];
      media?: import("./types").ChatMediaIn[];
    },
    opts?: { useLanggraph?: boolean },
  ) =>
    post<{ output: unknown; steps: unknown[] }>(`/flows/${flowId}/run`, {
      inputs: payload.inputs,
      kb_ids: payload.kb_ids ?? [],
      ...(payload.media?.length ? { media: payload.media } : {}),
      ...(opts?.useLanggraph ? { use_langgraph: true } : {}),
    }),

  getKbQuota: () => get<KbQuota>("/kb/quota"),

  listKbs: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<KnowledgeBase>(`/kb?${buildPageQuery(page, size)}`),
  createKb: (payload: {
    name: string;
    description?: string;
    embedding_model_config_id?: string;
    chunk_size?: number;
    chunk_overlap?: number;
    retrieval_mode?: "vector" | "hybrid";
    hybrid_alpha?: number;
    rerank_model_config_id?: string | null;
    rerank_candidate_k?: number;
    is_public?: boolean;
  }) => post<KnowledgeBase>("/kb", payload),
  updateKb: (
    kbId: string,
    payload: {
      name?: string;
      description?: string | null;
      chunk_size?: number;
      chunk_overlap?: number;
      retrieval_mode?: "vector" | "hybrid";
      hybrid_alpha?: number;
      rerank_model_config_id?: string | null;
      rerank_candidate_k?: number;
      is_public?: boolean;
    },
  ) => patch<KnowledgeBase>(`/kb/${kbId}`, payload),
  deleteKb: (kbId: string) => http.delete(`/kb/${kbId}`).then(() => undefined),

  listAgents: (
    page = 1,
    size = DEFAULT_PAGE_SIZE,
    agentType?: import("./types").AgentType,
    categoryId?: string,
    tagIds?: string[],
  ) => {
    let q = buildPageQuery(page, size);
    if (agentType) q += `&agent_type=${agentType}`;
    if (categoryId) q += `&category_id=${categoryId}`;
    q = appendTagIds(q, tagIds);
    return getPage<Agent>(`/agents?${q}`);
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
  getAgentStats: (agentId: string, days = 7) =>
    get<AgentStats>(`/agents/${agentId}/stats?days=${days}`),
  getAgentArchitecture: (agentId: string) =>
    get<AgentArchitecture>(`/agents/${agentId}/architecture`),
  listAgentSchedules: (agentId: string, page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<import("./types").AgentSchedule>(
      `/agents/${agentId}/schedules?${buildPageQuery(page, size)}`,
    ),
  createAgentSchedule: (agentId: string, payload: import("./types").AgentScheduleInput) =>
    post<import("./types").AgentSchedule>(`/agents/${agentId}/schedules`, payload),
  updateAgentSchedule: (
    agentId: string,
    scheduleId: string,
    payload: Partial<import("./types").AgentScheduleInput>,
  ) =>
    patch<import("./types").AgentSchedule>(`/agents/${agentId}/schedules/${scheduleId}`, payload),
  deleteAgentSchedule: (agentId: string, scheduleId: string) =>
    http.delete(`/agents/${agentId}/schedules/${scheduleId}`).then(() => undefined),
  createAgent: (payload: {
    agent_type?: import("./types").AgentType;
    category_id?: string | null;
    tag_ids?: string[];
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
      category_id?: string | null;
      tag_ids?: string[];
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
  // --- 智能体对话（chains §5；conversation_id 与 chat-sessions 会话 id 一致）---
  chatAgent: (
    agentId: string,
    query: string,
    opts?: {
      conversationId?: string;
      media?: import("./types").ChatMediaIn[];
      toolConfirmed?: boolean;
      pendingToolSlug?: string;
      pendingToolParams?: Record<string, unknown>;
    },
  ) =>
    postWithTrace<ChatResponse>(`/agents/${agentId}/chat`, {
      query,
      ...(opts?.media?.length ? { media: opts.media } : {}),
      ...(opts?.conversationId ? { conversation_id: opts.conversationId } : {}),
      ...(opts?.toolConfirmed ? { tool_confirmed: true } : {}),
      ...(opts?.pendingToolSlug ? { pending_tool_slug: opts.pendingToolSlug } : {}),
      ...(opts?.pendingToolParams ? { pending_tool_params: opts.pendingToolParams } : {}),
    }) as Promise<ChatAgentResult>,

  /** 鉴权拉取附件字节并返回 blob URL（用于对话缩略图，非签名 OSS） */
  fetchAttachmentPreviewUrl: async (attachmentId: string) => {
    const res = await http.get<Blob>(`/attachments/${attachmentId}/content`, {
      responseType: "blob",
    });
    return URL.createObjectURL(res.data);
  },

  getKb: (kbId: string) => get<KnowledgeBase>(`/kb/${kbId}`),
  listDocuments: (kbId: string, page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<Document>(`/kb/${kbId}/documents?${buildPageQuery(page, size)}`),
  listDocumentChunks: (kbId: string, documentId: string, page = 1, size = 20) =>
    getPage<DocumentChunk>(
      `/kb/${kbId}/documents/${documentId}/chunks?${buildPageQuery(page, size)}`,
    ),
  uploadDocument: async (kbId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await http.post<ApiResponse<Document>>(`/kb/${kbId}/documents`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return unwrap(res.data);
  },
  deleteDocument: (kbId: string, documentId: string) =>
    http
      .delete<ApiResponse<null>>(`/kb/${kbId}/documents/${documentId}`)
      .then((res) => {
        unwrap(res.data);
      }),
  retryDocument: (kbId: string, documentId: string) =>
    post<Document>(`/kb/${kbId}/documents/${documentId}/retry`),
  searchKb: (
    kbId: string,
    query: string,
    opts?: { top_k?: number; mode?: "default" | "vector" | "hybrid" },
  ) =>
    post<{
      query: string;
      mode: string;
      hits: {
        content: string;
        score: number;
        score_vector?: number | null;
        score_keyword?: number | null;
        filename?: string;
      }[];
    }>(`/kb/${kbId}/search`, {
      query,
      top_k: opts?.top_k ?? 5,
      mode: opts?.mode ?? "default",
    }),

  listKbSearchLogs: (kbId: string, page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<KbSearchLog>(`/kb/${kbId}/search-logs?${buildPageQuery(page, size)}`),

  listAttachments: (
    page = 1,
    size = DEFAULT_PAGE_SIZE,
    opts?: { purpose?: string; resource_type?: string; resource_id?: string },
  ) => {
    const q = new URLSearchParams(buildPageQuery(page, size));
    if (opts?.purpose) q.set("purpose", opts.purpose);
    if (opts?.resource_type) q.set("resource_type", opts.resource_type);
    if (opts?.resource_id) q.set("resource_id", opts.resource_id);
    return getPage<Attachment>(`/attachments?${q.toString()}`);
  },
  uploadAttachment: async (
    file: File,
    opts?: { purpose?: string; resource_type?: string; resource_id?: string },
  ) => {
    const form = new FormData();
    form.append("file", file);
    if (opts?.purpose) form.append("purpose", opts.purpose);
    if (opts?.resource_type) form.append("resource_type", opts.resource_type);
    if (opts?.resource_id) form.append("resource_id", opts.resource_id);
    const res = await http.post<ApiResponse<Attachment>>("/attachments", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return unwrap(res.data);
  },
  getAttachment: (id: string) => get<Attachment>(`/attachments/${id}`),
  deleteAttachment: (id: string) =>
    http.delete(`/attachments/${id}`).then(() => undefined),

  listMediaAssets: (
    page = 1,
    size = DEFAULT_PAGE_SIZE,
    opts?: { kind?: string; source?: string; has_kb_document?: boolean },
  ) => {
    const q = new URLSearchParams(buildPageQuery(page, size));
    if (opts?.kind) q.set("kind", opts.kind);
    if (opts?.source) q.set("source", opts.source);
    if (opts?.has_kb_document !== undefined) {
      q.set("has_kb_document", String(opts.has_kb_document));
    }
    return getPage<import("./types").MediaAsset>(`/media-assets?${q.toString()}`);
  },
  getMediaAsset: (id: string) => get<import("./types").MediaAsset>(`/media-assets/${id}`),
  updateMediaAsset: (id: string, body: { title?: string; tags?: string[] }) =>
    http.patch<ApiResponse<import("./types").MediaAsset>>(`/media-assets/${id}`, body).then((r) =>
      unwrap(r.data),
    ),
  deleteMediaAsset: (id: string) =>
    http.delete(`/media-assets/${id}`).then(() => undefined),
  promoteMediaAssetToKb: (
    id: string,
    body: { kb_id: string; filename?: string; run_parse?: boolean },
  ) =>
    http
      .post<ApiResponse<import("./types").MediaAsset>>(`/media-assets/${id}/promote-to-kb`, body)
      .then((r) => unwrap(r.data)),

  // --- 各域枚举元数据：backend tenant/*/meta.py → GET */meta → hooks/use-*-meta → lib/*-labels（见 lib/enum-meta.ts、docs/guides/hooks.md §9）---
  getHookMeta: () => get<import("./types").HookMeta>("/hooks/meta"),
  getComplianceMeta: () => get<import("./types").ComplianceMeta>("/compliance/meta"),
  getFlowMeta: () => get<import("./types").FlowMeta>("/flows/meta"),
  getFlowTemplates: () =>
    get<import("./types").FlowTemplatesResponse>("/flows/templates"),
  getKbMeta: () => get<import("./types").KbMeta>("/kb/meta"),
  getToolsMeta: () => get<import("./types").ToolsMeta>("/tools/meta"),
  getAgentMeta: () => get<import("./types").AgentMeta>("/agents/meta"),
  getPromptMeta: () => get<import("./types").PromptMeta>("/prompt-templates/meta"),
  getSkillMeta: () => get<import("./types").SkillMeta>("/skill-packages/meta"),
  getA2aMeta: () => get<import("./types").A2aMeta>("/a2a/peers/meta"),
  getMonitorMeta: () => get<import("./types").MonitorMeta>("/monitor/meta"),
  getTaskMeta: () => get<import("./types").TaskMeta>("/tasks/meta"),
  getCategoryMeta: () => get<import("./types").CategoryMeta>("/categories/meta"),
  getTagMeta: () => get<import("./types").TagMeta>("/tags/meta"),
  getAuditMeta: () => get<import("./types").AuditMeta>("/audit/meta"),
  getMarketplaceMeta: () => get<import("./types").MarketplaceMeta>("/marketplace/meta"),
  getMcpMeta: () => get<import("./types").McpMeta>("/mcp/meta"),
  getAttachmentMeta: () => get<import("./types").AttachmentMeta>("/attachments/meta"),
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
  listHookExecutions: (hookId: string, page = 1, size = 10) =>
    getPage<import("./types").HookExecutionLog>(
      `/hooks/executions?hook_id=${hookId}&${buildPageQuery(page, size)}`,
    ),

  listToolCatalog: (source?: string, categoryId?: string, tagIds?: string[]) => {
    const q = new URLSearchParams();
    if (source) q.set("source", source);
    if (categoryId) q.set("category_id", categoryId);
    tagIds?.forEach((id) => q.append("tag_ids", id));
    const qs = q.toString();
    return get<import("./types").ToolCatalogItem[]>(`/tools/catalog${qs ? `?${qs}` : ""}`);
  },
  listCustomTools: (page = 1, size = DEFAULT_PAGE_SIZE, categoryId?: string, tagIds?: string[]) => {
    let qs = buildPageQuery(page, size);
    if (categoryId) qs += `&category_id=${categoryId}`;
    qs = appendTagIds(qs, tagIds);
    return getPage<import("./types").CustomTool>(`/tools?${qs}`);
  },
  getCustomTool: (id: string) => get<import("./types").CustomTool>(`/tools/${id}`),
  createCustomTool: (payload: import("./types").ToolCreatePayload) =>
    post<import("./types").CustomTool>("/tools", { tool_type: "http", ...payload }),
  updateCustomTool: (id: string, payload: Partial<import("./types").ToolCreatePayload & { is_active?: boolean }>) =>
    patch<import("./types").CustomTool>(`/tools/${id}`, payload),
  deleteCustomTool: (id: string) => http.delete(`/tools/${id}`).then(() => undefined),
  invokeTool: (
    name: string,
    params: Record<string, unknown>,
    toolId?: string,
    confirmed = false,
  ) =>
    post<{
      tool: string;
      source: string;
      status: string;
      output: Record<string, unknown>;
      pending?: import("./types").PendingToolCall | null;
    }>(`/tools/${encodeURIComponent(name)}/invoke`, {
      params,
      tool_id: toolId || null,
      confirmed,
    }),
  listToolInvocationLogs: (page = 1, size = DEFAULT_PAGE_SIZE, toolSlug?: string) => {
    const q = new URLSearchParams(buildPageQuery(page, size));
    if (toolSlug) q.set("tool_slug", toolSlug);
    return getPage<import("./types").ToolInvocationLog>(`/tools/invocation-logs?${q.toString()}`);
  },
  listBuiltinTools: () => get<Record<string, string>[]>("/tools/builtin"),

  // --- 技能包（SKILL.md 落盘，见 docs/guides/skill-packages.md）---
  listSkillPackages: (page = 1, size = DEFAULT_PAGE_SIZE, categoryId?: string, tagIds?: string[]) => {
    let q = buildPageQuery(page, size);
    if (categoryId) q += `&category_id=${encodeURIComponent(categoryId)}`;
    q = appendTagIds(q, tagIds);
    return getPage<SkillPackage>(`/skill-packages?${q}`);
  },
  getSkillPackage: (id: string) => get<SkillPackage>(`/skill-packages/${id}`),
  createSkillPackageBlank: (payload: {
    name: string;
    description?: string;
    category_id: string;
    tag_ids?: string[];
  }) => post<SkillPackage>("/skill-packages/blank", payload),
  createSkillPackage: (payload: {
    name: string;
    description?: string;
    category_id?: string;
    tag_ids?: string[];
    tool_names?: string[];
    prompt_snippet?: string;
  }) => post<SkillPackage>("/skill-packages", payload),
  updateSkillPackage: (
    id: string,
    payload: {
      name?: string;
      description?: string;
      category_id?: string | null;
      tag_ids?: string[];
      tool_names?: string[];
      prompt_snippet?: string;
      is_active?: boolean;
    },
  ) => patch<SkillPackage>(`/skill-packages/${id}`, payload),
  deleteSkillPackage: (id: string) =>
    http.delete(`/skill-packages/${id}`).then(() => undefined),
  listSkillFiles: (id: string) => get<import("./types").SkillFileNode[]>(`/skill-packages/${id}/files`),
  getSkillFile: (id: string, path: string) =>
    get<{ path: string; content: string }>(
      `/skill-packages/${id}/file?path=${encodeURIComponent(path)}`,
    ),
  putSkillFile: (id: string, payload: { path: string; content: string }) =>
    put<{ path: string; content: string }>(`/skill-packages/${id}/file`, payload),
  reindexSkillPackage: (id: string) => post<SkillPackage>(`/skill-packages/${id}/reindex`, {}),
  deleteSkillFile: (id: string, path: string) =>
    http.delete(`/skill-packages/${id}/file?path=${encodeURIComponent(path)}`).then(() => undefined),
  importSkillLocal: (payload: {
    category_id: string;
    local_path: string;
    overwrite_existing?: boolean;
  }) => post<import("./types").SkillImportResult>("/skill-packages/import/local", payload),
  importSkillGit: (payload: {
    category_id: string;
    repo_url: string;
    overwrite_existing?: boolean;
  }) => post<import("./types").SkillImportResult>("/skill-packages/import/git", payload),
  importSkillZip: async (
    categoryId: string,
    file: File,
    overwriteExisting = false,
  ) => {
    const form = new FormData();
    form.append("file", file);
    const q = `category_id=${encodeURIComponent(categoryId)}&overwrite_existing=${overwriteExisting}`;
    const res = await http.post<ApiResponse<import("./types").SkillImportResult>>(
      `/skill-packages/import/zip?${q}`,
      form,
      { headers: { "Content-Type": "multipart/form-data" } },
    );
    return unwrap(res.data);
  },

  listMcpServices: (page = 1, size = DEFAULT_PAGE_SIZE, transport?: string) => {
    const q = buildPageQuery(page, size);
    const extra = transport ? `&transport=${encodeURIComponent(transport)}` : "";
    return getPage<McpService>(`/mcp?${q}${extra}`);
  },
  createMcpService: (payload: {
    name: string;
    transport: string;
    endpoint_url?: string;
    description?: string;
    connection_config?: Record<string, unknown>;
  }) => post<McpService>("/mcp", payload),
  updateMcpService: (
    id: string,
    payload: {
      name?: string;
      transport?: string;
      endpoint_url?: string;
      description?: string;
      connection_config?: Record<string, unknown>;
    },
  ) => patch<McpService>(`/mcp/${id}`, payload),
  deleteMcpService: (id: string) => http.delete(`/mcp/${id}`).then(() => undefined),
  syncMcpService: (serviceId: string) =>
    post<{ tools: Record<string, unknown>[]; synced_at: string }>(`/mcp/${serviceId}/sync`),
  invokeMcpTool: (serviceId: string, toolName: string, params: Record<string, unknown>) =>
    post<{ service_id: string; tool_name: string; output: Record<string, unknown> }>(
      `/mcp/${serviceId}/tools/${encodeURIComponent(toolName)}/invoke`,
      { params },
    ),

  getWorkbenchOverview: () => get<WorkbenchOverview>("/workbench/overview"),

  getMonitorStats: () => get<MonitorStats>("/monitor/stats"),
  getMonitorReport: () => get<MonitorReport>("/monitor/report"),
  exportMonitorReport: () =>
    http.get("/monitor/report/export", { responseType: "blob" }).then((res) => res.data as Blob),
  getMonitorHealth: () =>
    get<{ healthy: boolean; status: string; components: Record<string, unknown> }>("/monitor/health"),
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
