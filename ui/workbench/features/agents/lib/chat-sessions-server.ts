/**
 * 服务端对话会话与本地 chat-sessions 合并。
 */

import { api } from "@/lib/api";
import {
  getSession,
  listSessions,
  type ChatMessage,
  type ChatSession,
  updateSession,
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

function shouldReplaceLocal(local: ChatSession, serverUpdatedMs: number, serverCount: number): boolean {
  if (serverCount > (local.messageCount ?? local.messages.length)) return true;
  if (serverUpdatedMs > local.updatedAt) return true;
  return false;
}

export async function mergeServerChatSessions(agentId: string): Promise<void> {
  const page = await api.listAgentChatSessions(agentId, 1, 80);
  for (const summary of page.items) {
    const local = getSession(agentId, summary.id);
    const serverUpdatedMs = new Date(summary.updated_at).getTime();
    if (local && !shouldReplaceLocal(local, serverUpdatedMs, summary.message_count)) {
      continue;
    }
    const detail = await api.getAgentChatSession(agentId, summary.id);
    importServerSession(agentId, detail);
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
      ? ((detail as { message_count?: number }).message_count ?? (local.messageCount ?? merged.length))
      : merged.length;
    updateSession(agentId, detail.id, {
      title: detail.title,
      messages: merged,
      updatedAt,
    } as Parameters<typeof updateSession>[2]);
    const patched = getSession(agentId, detail.id);
    if (patched && msgCount !== patched.messages.length) {
      // 通过原生的 localStorage 路径 patch messageCount
      patchSessionMeta(agentId, detail.id, { messageCount: msgCount });
    }
    return patched ?? { ...local, title: detail.title, messages: merged, updatedAt };
  }

  const storeKey = "agents-chat-sessions-v1";
  const raw = localStorage.getItem(storeKey);
  const store = raw ? (JSON.parse(raw) as Record<string, { activeSessionId: string | null; sessions: ChatSession[] }>) : {};
  if (!store[agentId]) {
    store[agentId] = { activeSessionId: null, sessions: [] };
  }
  const session: ChatSession = {
    id: detail.id,
    agentId,
    title: detail.title,
    createdAt,
    updatedAt,
    messages: serverMessages,
  };
  store[agentId].sessions = [session, ...store[agentId].sessions.filter((s) => s.id !== detail.id)].slice(0, 80);
  localStorage.setItem(storeKey, JSON.stringify(store));
  return session;
}

/** 合并本地与服务端消息：以服务端为准，去重（按 role+content 粗略去重）。 */
function mergeMessages(localMessages: ChatMessage[], serverMessages: ChatMessage[]): ChatMessage[] {
  const serverKeys = new Set(serverMessages.map((m) => `${m.role}|${m.content?.slice(0, 80)}`));
  const localOlder = localMessages.filter((m) => !serverKeys.has(`${m.role}|${m.content?.slice(0, 80)}`));
  return [...localOlder, ...serverMessages];
}

/** 更新 session 的 messageCount 元数据（不改变 messages 数组）。 */
function patchSessionMeta(agentId: string, sessionId: string, patch: { messageCount: number }) {
  const storeKey = "agents-chat-sessions-v1";
  const raw = localStorage.getItem(storeKey);
  if (!raw) return;
  try {
    const store = JSON.parse(raw) as Record<string, { activeSessionId: string | null; sessions: ChatSession[] }>;
    const b = store[agentId];
    if (!b) return;
    const idx = b.sessions.findIndex((s) => s.id === sessionId);
    if (idx < 0) return;
    b.sessions[idx] = { ...b.sessions[idx], messageCount: patch.messageCount };
    localStorage.setItem(storeKey, JSON.stringify(store));
  } catch {
    /* ignore */
  }
}

export async function fetchServerSessionIntoLocal(agentId: string, sessionId: string): Promise<ChatSession | null> {
  try {
    const detail = await api.getAgentChatSession(agentId, sessionId);
    return importServerSession(agentId, detail);
  } catch {
    return getSession(agentId, sessionId);
  }
}

export function listMergedSessions(agentId: string): ChatSession[] {
  return listSessions(agentId);
}
