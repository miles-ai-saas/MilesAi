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
    ...(m.media?.length ? { media: m.media as ChatMessage["media"] } : {}),
    ...(m.artifacts?.length ? { artifacts: m.artifacts as ChatMessage["artifacts"] } : {}),
    ...(m.steps?.length ? { steps: m.steps as Record<string, unknown>[] } : {}),
    ...(m.trace_id ? { traceId: m.trace_id } : {}),
  }));
}

function shouldReplaceLocal(local: ChatSession, serverUpdatedMs: number, serverCount: number): boolean {
  if (serverCount > local.messages.length) return true;
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
  const messages = mapServerMessages(detail.messages);
  const updatedAt = new Date(detail.updated_at).getTime();
  const createdAt = new Date(detail.created_at).getTime();
  const local = getSession(agentId, detail.id);
  if (local) {
    updateSession(agentId, detail.id, {
      title: detail.title,
      messages,
      updatedAt,
    });
    return { ...local, title: detail.title, messages, updatedAt };
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
    messages,
  };
  store[agentId].sessions = [session, ...store[agentId].sessions.filter((s) => s.id !== detail.id)].slice(0, 80);
  localStorage.setItem(storeKey, JSON.stringify(store));
  return session;
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
