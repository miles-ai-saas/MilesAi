import type { Agent, AgentStats, AgentArchitecture, ChatResponse, ChatAgentResult } from "../types";
import { get, getPage, post, patch, http, postWithTrace } from "./client";
import { appendTagIds } from "./query";
import { buildPageQuery, DEFAULT_PAGE_SIZE } from "../pagination";

export const agentsApi = {
  listAgents: (page = 1, size = DEFAULT_PAGE_SIZE, agentType?: import("../types").AgentType, categoryId?: string, tagIds?: string[]) => {
    let q = buildPageQuery(page, size);
    if (agentType) q += `&agent_type=${agentType}`;
    if (categoryId) q += `&category_id=${categoryId}`;
    q = appendTagIds(q, tagIds);
    return getPage<Agent>(`/agents?${q}`);
  },

  listA2aPeers: (page = 1, size = DEFAULT_PAGE_SIZE) => getPage<import("../types").A2aPeer>(`/a2a/peers?${buildPageQuery(page, size)}`),

  createA2aPeer: (payload: { name: string; base_url: string; description?: string; auth_config?: Record<string, unknown> }) =>
    post<import("../types").A2aPeer>("/a2a/peers", payload),

  probeA2aPeer: (baseUrl: string) => post<import("../types").A2aPeerProbeResult>("/a2a/peers/probe", { base_url: baseUrl }),

  syncA2aPeerCard: (peerId: string) => post<import("../types").A2aPeerSyncResult>(`/a2a/peers/${peerId}/sync-card`, {}),

  deleteA2aPeer: (peerId: string) => http.delete(`/a2a/peers/${peerId}`).then(() => undefined),

  getAgent: (agentId: string) => get<Agent>(`/agents/${agentId}`),

  getAgentStats: (agentId: string, days = 7) => get<AgentStats>(`/agents/${agentId}/stats?days=${days}`),

  getAgentArchitecture: (agentId: string) => get<AgentArchitecture>(`/agents/${agentId}/architecture`),

  listAgentSchedules: (agentId: string, page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<import("../types").AgentSchedule>(`/agents/${agentId}/schedules?${buildPageQuery(page, size)}`),

  createAgentSchedule: (agentId: string, payload: import("../types").AgentScheduleInput) =>
    post<import("../types").AgentSchedule>(`/agents/${agentId}/schedules`, payload),

  updateAgentSchedule: (agentId: string, scheduleId: string, payload: Partial<import("../types").AgentScheduleInput>) =>
    patch<import("../types").AgentSchedule>(`/agents/${agentId}/schedules/${scheduleId}`, payload),

  deleteAgentSchedule: (agentId: string, scheduleId: string) => http.delete(`/agents/${agentId}/schedules/${scheduleId}`).then(() => undefined),

  listAgentScheduleRuns: (agentId: string, scheduleId: string, page = 1, size = 10) =>
    getPage<import("../types").AgentScheduleRun>(`/agents/${agentId}/schedules/${scheduleId}/runs?${buildPageQuery(page, size)}`),

  listAgentCallRecords: (
    agentId: string,
    page = 1,
    size = DEFAULT_PAGE_SIZE,
    opts?: {
      status?: string;
      conversation_id?: string;
      route?: string;
      q?: string;
      from?: string;
      to?: string;
    },
  ) => {
    let q = buildPageQuery(page, size);
    if (opts?.status) q += `&status=${encodeURIComponent(opts.status)}`;
    if (opts?.conversation_id) q += `&conversation_id=${encodeURIComponent(opts.conversation_id)}`;
    if (opts?.route) q += `&route=${encodeURIComponent(opts.route)}`;
    if (opts?.q) q += `&q=${encodeURIComponent(opts.q)}`;
    if (opts?.from) q += `&from=${encodeURIComponent(opts.from)}`;
    if (opts?.to) q += `&to=${encodeURIComponent(opts.to)}`;
    return getPage<import("../types").AgentCallRecord>(`/agents/${agentId}/call-records?${q}`);
  },

  getAgentCallRecord: (agentId: string, callId: string) =>
    get<import("../types").AgentCallRecordDetail>(`/agents/${agentId}/call-records/${callId}`),

  listAgentChatSessions: (agentId: string, page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<import("../types").AgentChatSessionSummary>(`/agents/${agentId}/chat-sessions?${buildPageQuery(page, size)}`),

  getAgentChatSession: (agentId: string, sessionId: string) =>
    get<import("../types").ChatSessionDetail>(`/agents/${agentId}/chat-sessions/${sessionId}`),

  createAgentChatSession: (agentId: string, payload: { id?: string; title?: string }) =>
    post<import("../types").AgentChatSessionSummary>(`/agents/${agentId}/chat-sessions`, payload),

  updateAgentChatSession: (agentId: string, sessionId: string, payload: { title: string }) =>
    patch<import("../types").AgentChatSessionSummary>(`/agents/${agentId}/chat-sessions/${sessionId}`, payload),

  deleteAgentChatSession: (agentId: string, sessionId: string) =>
    http.delete(`/agents/${agentId}/chat-sessions/${sessionId}`).then(() => undefined),

  createAgent: (payload: {
    agent_type?: import("../types").AgentType;
    category_id?: string | null;
    tag_ids?: string[];
    name: string;
    description?: string;
    kb_ids?: string[];
    sub_agents?: import("../types").SubAgentBindingInput[];
    a2a_peers?: import("../types").A2aPeerRefInput[];
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
      sub_agents?: import("../types").SubAgentBindingInput[];
      a2a_peers?: import("../types").A2aPeerRefInput[];
      published_flow_id?: string | null;
      system_prompt?: string;
      prompt_template_id?: string | null;
      model_config_id?: string | null;
      config?: Record<string, unknown>;
    },
  ) => patch<Agent>(`/agents/${agentId}`, payload),

  deleteAgent: (agentId: string) => http.delete(`/agents/${agentId}`).then(() => undefined),
  // --- 智能体对话（chains §5；conversation_id 与 chat-sessions 会话 id 一致）---,

  chatAgent: (
    agentId: string,
    query: string,
    opts?: {
      conversationId?: string;
      media?: import("../types").ChatMediaIn[];
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
};
