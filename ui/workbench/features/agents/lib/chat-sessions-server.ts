/**
 * 服务端对话会话与本地 chat-sessions 合并。
 */

import { api } from "@/lib/api";
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
      updatedAt,
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
  const serverSortIndices = new Set<number>();
  const serverContentKeys = new Set<string>();
  for (const m of serverMessages) {
    if (m.sortIndex != null) {
      serverSortIndices.add(m.sortIndex);
    } else {
      serverContentKeys.add(`${m.role}|${m.content.slice(0, 80)}`);
    }
  }
  const localOlder = localMessages.filter((m) => {
    if (m.sortIndex != null) return !serverSortIndices.has(m.sortIndex);
    return !serverContentKeys.has(`${m.role}|${m.content.slice(0, 80)}`);
  });
  return [...localOlder, ...serverMessages];
}

export async function fetchServerSessionIntoLocal(agentId: string, sessionId: string): Promise<ChatSession | null> {
  try {
    const detail = await api.getAgentChatSession(agentId, sessionId);
    return importServerSession(agentId, detail);
  } catch {
    return getSession(agentId, sessionId);
  }
}
