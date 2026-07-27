/**
 * 服务端对话会话与本地 chat-sessions 合并。
 */

import { api } from "@/lib/api";
import { effectiveArtifactStatus } from "@/lib/generative-jobs";
import {
  getSession,
  importSession,
  updateSession,
  type ChatMessage,
  type ChatSession,
} from "@/features/agents/lib/chat-sessions";
import type { ChatSessionDetail } from "@/lib/types";

function mapServerMessages(messages: ChatSessionDetail["messages"]): ChatMessage[] {
  return messages.map((m) => ({
    role: m.role as "user" | "assistant",
    content: m.content,
    sortIndex: m.sort_index,
    ...(m.media?.length ? { media: m.media as ChatMessage["media"] } : {}),
    ...(m.artifacts?.length ? { artifacts: m.artifacts as ChatMessage["artifacts"] } : {}),
    ...(m.steps?.length ? { steps: m.steps as Record<string, unknown>[] } : {}),
    ...(m.trace_id ? { traceId: m.trace_id } : {}),
  }));
}

export { mapServerMessages };

function shouldReplaceLocal(local: ChatSession, serverUpdatedMs: number, serverCount: number): boolean {
  if (serverCount > (local.messageCount ?? local.messages.length)) return true;
  if (serverUpdatedMs > local.updatedAt) return true;
  return false;
}

function messageContentKey(m: ChatMessage): string {
  return `${m.role}|${m.content.slice(0, 80)}`;
}

/** 本地已把生图校正为 success 时，勿被服务端仍存的 pending 覆盖。 */
function artifactCompleteness(m: ChatMessage): number {
  let best = 0;
  for (const a of m.artifacts ?? []) {
    const s = effectiveArtifactStatus(a);
    if (s === "success" && (a.attachment_id || a.media_asset_id)) best = Math.max(best, 4);
    else if (s === "success") best = Math.max(best, 3);
    else if (s === "failed" || s === "cancelled") best = Math.max(best, 2);
    else if (s === "running") best = Math.max(best, 1);
  }
  return best;
}

function preferRicherArtifacts(base: ChatMessage, other?: ChatMessage): ChatMessage {
  if (!other) return base;
  if (artifactCompleteness(other) > artifactCompleteness(base)) {
    return {
      ...base,
      artifacts: other.artifacts,
      content: base.content || other.content,
      steps: base.steps?.length ? base.steps : other.steps,
      traceId: base.traceId || other.traceId,
    };
  }
  return base;
}

export async function mergeServerChatSessions(agentId: string): Promise<void> {
  // 首屏只拉最近一页摘要，且最多补齐少量详情，避免本地已有大量会话时刷爆 API / localStorage
  const page = await api.listAgentChatSessions(agentId, 1, 30);
  let fetched = 0;
  const MAX_DETAIL_FETCH = 8;
  for (const summary of page.items) {
    const local = getSession(agentId, summary.id);
    const serverUpdatedMs = new Date(summary.updated_at).getTime();
    if (local && !shouldReplaceLocal(local, serverUpdatedMs, summary.message_count)) {
      continue;
    }
    if (fetched >= MAX_DETAIL_FETCH) break;
    const detail = await api.getAgentChatSession(agentId, summary.id);
    importServerSession(agentId, detail);
    fetched += 1;
  }
}

export function importServerSession(agentId: string, detail: ChatSessionDetail): ChatSession {
  const serverMessages = mapServerMessages(detail.messages);
  const updatedAt = new Date(detail.updated_at).getTime();
  const createdAt = new Date(detail.created_at).getTime();
  const local = getSession(agentId, detail.id);

  if (local) {
    // 服务端返回的是最新 N 条，merge 到本地（保留本地已有的更早消息）
    const merged = mergeMessages(local.messages, serverMessages);
    const msgCount = detail.has_more
      ? (detail.message_count ?? (local.messageCount ?? merged.length))
      : merged.length;
    updateSession(agentId, detail.id, {
      title: detail.title,
      messages: merged,
      // 保留较新的 updatedAt，避免随后又被陈旧服务端时间反复覆盖
      updatedAt: Math.max(local.updatedAt, updatedAt),
      messageCount: msgCount,
    });
    return getSession(agentId, detail.id) ?? { ...local, title: detail.title, messages: merged, updatedAt };
  }

  const session: ChatSession = {
    id: detail.id,
    agentId,
    title: detail.title,
    createdAt,
    updatedAt,
    messages: serverMessages,
  };
  importSession(agentId, session);
  return session;
}

/** 合并本地与服务端消息：优先用 sortIndex 去重，无 sortIndex 时回退到 role+content 模糊匹配。 */
export function mergeMessages(localMessages: ChatMessage[], serverMessages: ChatMessage[]): ChatMessage[] {
  const localBySort = new Map<number, ChatMessage>();
  const localByContent = new Map<string, ChatMessage>();
  for (const m of localMessages) {
    if (m.sortIndex != null) localBySort.set(m.sortIndex, m);
    localByContent.set(messageContentKey(m), m);
  }

  const serverSortIndices = new Set<number>();
  const serverContentKeys = new Set<string>();
  const mergedServer = serverMessages.map((sm) => {
    if (sm.sortIndex != null) {
      serverSortIndices.add(sm.sortIndex);
      return preferRicherArtifacts(sm, localBySort.get(sm.sortIndex) ?? localByContent.get(messageContentKey(sm)));
    }
    serverContentKeys.add(messageContentKey(sm));
    return preferRicherArtifacts(sm, localByContent.get(messageContentKey(sm)));
  });

  const localOlder = localMessages.filter((m) => {
    if (m.sortIndex != null) return !serverSortIndices.has(m.sortIndex);
    return !serverContentKeys.has(messageContentKey(m));
  });
  return [...localOlder, ...mergedServer];
}

export async function fetchServerSessionIntoLocal(agentId: string, sessionId: string): Promise<ChatSession | null> {
  try {
    const detail = await api.getAgentChatSession(agentId, sessionId);
    return importServerSession(agentId, detail);
  } catch {
    return getSession(agentId, sessionId);
  }
}
