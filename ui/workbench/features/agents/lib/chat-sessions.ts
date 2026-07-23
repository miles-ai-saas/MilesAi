/**
 * 对话工作台本地多会话（链路 §5，见 `lib/chains.ts`）。
 * `session.id` 作为 `api.chatAgent` 的 `conversation_id`；消息与 steps 仅存浏览器 localStorage。
 */

export type ChatMessageMedia = {
  attachment_id: string;
  preview_url?: string;
  filename?: string;
};

export type ChatMessageArtifact = {
  kind: string;
  attachment_id?: string | null;
  mime_type?: string | null;
  preview_url?: string;
  caption?: string | null;
  status?: "pending" | "running" | "success" | "failed" | "cancelled" | null;
  job_id?: string | null;
  media_asset_id?: string | null;
  progress_percent?: number | null;
  progress_message?: string | null;
  error_message?: string | null;
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  /** 服务端 sort_index，用于游标分页；本地消息可能为 undefined */
  sortIndex?: number;
  media?: ChatMessageMedia[];
  artifacts?: ChatMessageArtifact[];
  steps?: Record<string, unknown>[];
  traceId?: string;
};

export type ChatSession = {
  id: string;
  agentId: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: ChatMessage[];
  /** 服务端消息总数（可能大于本地 messages 数量，用于判断是否需要从服务端拉取更多） */
  messageCount?: number;
};

type AgentSessionBucket = {
  activeSessionId: string | null;
  sessions: ChatSession[];
};

type Store = Record<string, AgentSessionBucket>;

const STORAGE_KEY = "agents-chat-sessions-v1";
const MAX_SESSIONS_PER_AGENT = 80;
export const MESSAGES_PAGE_SIZE = 10;
export const MAX_SESSION_TITLE_LENGTH = 64;

/** 获取 session 中最新 N 条消息（用于初始加载）。 */
export function getLatestMessages(session: ChatSession, limit = MESSAGES_PAGE_SIZE): ChatMessage[] {
  const total = session.messages.length;
  if (total <= limit) return [...session.messages];
  return session.messages.slice(total - limit);
}

/** 判断本地是否还有更多消息未展示（相对于当前 UI 消息数）。 */
export function hasMoreLocalMessages(session: ChatSession, uiMessageCount: number): boolean {
  return session.messages.length > uiMessageCount;
}

/** 获取当前 UI 消息之前的一批本地消息（最早的那批）。 */
export function getPreviousMessages(session: ChatSession, uiMessageCount: number, limit = MESSAGES_PAGE_SIZE): ChatMessage[] {
  const localCount = session.messages.length;
  const remaining = localCount - uiMessageCount;
  if (remaining <= 0) return [];
  const start = Math.max(0, localCount - uiMessageCount - limit);
  const end = localCount - uiMessageCount;
  return session.messages.slice(start, end);
}

function loadStore(): Store {
  if (typeof window === "undefined") return {};
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Store) : {};
  } catch {
    return {};
  }
}

function saveStore(store: Store) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
  } catch {
    /* ignore quota */
  }
}

function bucket(agentId: string, store: Store): AgentSessionBucket {
  if (!store[agentId]) {
    store[agentId] = { activeSessionId: null, sessions: [] };
  }
  return store[agentId];
}

export function listSessions(agentId: string): ChatSession[] {
  const store = loadStore();
  return [...(store[agentId]?.sessions ?? [])].sort((a, b) => b.updatedAt - a.updatedAt);
}

export function getActiveSessionId(agentId: string): string | null {
  return loadStore()[agentId]?.activeSessionId ?? null;
}

export function getSession(agentId: string, sessionId: string): ChatSession | null {
  return listSessions(agentId).find((s) => s.id === sessionId) ?? null;
}

export function setActiveSessionId(agentId: string, sessionId: string) {
  const store = loadStore();
  const b = bucket(agentId, store);
  if (b.sessions.some((s) => s.id === sessionId)) {
    b.activeSessionId = sessionId;
    saveStore(store);
  }
}

function createSessionId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  // HTTP 非安全上下文下 crypto.randomUUID 不可用，回退到 RFC4122 v4
  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }
  return `xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx`.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function createSession(agentId: string, title = "新对话"): ChatSession {
  const store = loadStore();
  const b = bucket(agentId, store);
  const session: ChatSession = {
    id: createSessionId(),
    agentId,
    title,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages: [],
  };
  b.sessions = [session, ...b.sessions].slice(0, MAX_SESSIONS_PER_AGENT);
  b.activeSessionId = session.id;
  saveStore(store);
  return session;
}

export function ensureActiveSession(agentId: string): ChatSession {
  const store = loadStore();
  const b = bucket(agentId, store);
  const active = b.activeSessionId ? b.sessions.find((s) => s.id === b.activeSessionId) : null;
  if (active) return active;
  if (b.sessions.length > 0) {
    const latest = [...b.sessions].sort((a, b) => b.updatedAt - a.updatedAt)[0];
    b.activeSessionId = latest.id;
    saveStore(store);
    return latest;
  }
  return createSession(agentId);
}

export function updateSession(agentId: string, sessionId: string, patch: Partial<Pick<ChatSession, "title" | "messages" | "updatedAt" | "messageCount">>) {
  const store = loadStore();
  const b = bucket(agentId, store);
  const idx = b.sessions.findIndex((s) => s.id === sessionId);
  if (idx < 0) return;
  b.sessions[idx] = {
    ...b.sessions[idx],
    ...patch,
    updatedAt: patch.updatedAt ?? Date.now(),
  };
  saveStore(store);
}

/** 导入一条已在服务端存在的会话（覆盖本地同 ID 记录）。 */
export function importSession(agentId: string, session: ChatSession) {
  const store = loadStore();
  const b = bucket(agentId, store);
  b.sessions = [session, ...b.sessions.filter((s) => s.id !== session.id)].slice(0, MAX_SESSIONS_PER_AGENT);
  saveStore(store);
}

export function appendTurn(
  agentId: string,
  sessionId: string,
  userText: string,
  assistantText: string,
  steps: Record<string, unknown>[] = [],
  traceId?: string,
  userMedia?: ChatMessageMedia[],
  artifacts?: ChatMessageArtifact[],
) {
  const store = loadStore();
  const b = bucket(agentId, store);
  const idx = b.sessions.findIndex((s) => s.id === sessionId);
  if (idx < 0) return;
  const session = b.sessions[idx];
  const messages = [
    ...session.messages,
    {
      role: "user" as const,
      content: userText,
      ...(userMedia?.length ? { media: userMedia } : {}),
    },
    {
      role: "assistant" as const,
      content: assistantText,
      steps: steps.length ? steps : undefined,
      traceId: traceId || undefined,
      ...(artifacts?.length ? { artifacts } : {}),
    },
  ];
  let title = session.title;
  if (title === "新对话" && userText.trim()) {
    title = userText.trim().slice(0, 28) + (userText.length > 28 ? "…" : "");
  }
  b.sessions[idx] = {
    ...session,
    title,
    messages,
    updatedAt: Date.now(),
    ...(session.messageCount != null ? { messageCount: session.messageCount + 2 } : {}),
  };
  saveStore(store);
}

/** 重命名会话标题（仅本地存储）。 */
export function renameSession(agentId: string, sessionId: string, title: string): boolean {
  const trimmed = title.trim();
  if (!trimmed) return false;
  const session = getSession(agentId, sessionId);
  if (!session) return false;
  const next = trimmed.length > MAX_SESSION_TITLE_LENGTH ? `${trimmed.slice(0, MAX_SESSION_TITLE_LENGTH)}…` : trimmed;
  if (next === session.title) return true;
  updateSession(agentId, sessionId, { title: next });
  return true;
}

export function deleteSession(agentId: string, sessionId: string) {
  const store = loadStore();
  const b = bucket(agentId, store);
  b.sessions = b.sessions.filter((s) => s.id !== sessionId);
  if (b.activeSessionId === sessionId) {
    b.activeSessionId = b.sessions[0]?.id ?? null;
  }
  saveStore(store);
}

export type SessionGroup = { label: string; sessions: ChatSession[] };

export type PendingChatMedia = ChatMessageMedia & { local_preview: string };

export function groupSessionsByDate(sessions: ChatSession[]): SessionGroup[] {
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const now = new Date();
  const today = startOfDay(now);
  const yesterday = today - 86400000;

  const groups: Record<string, ChatSession[]> = {
    今天: [],
    昨天: [],
    更早: [],
  };

  for (const s of sessions) {
    const t = s.updatedAt;
    if (t >= today) groups["今天"].push(s);
    else if (t >= yesterday) groups["昨天"].push(s);
    else groups["更早"].push(s);
  }

  return (["今天", "昨天", "更早"] as const).map((label) => ({ label, sessions: groups[label] })).filter((g) => g.sessions.length > 0);
}
