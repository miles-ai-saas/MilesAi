"use client";

import { useCallback, useEffect, useState } from "react";
import type { AppRouterInstance } from "next/dist/shared/lib/app-router-context.shared-runtime";
import {
  createSession,
  deleteSession,
  ensureActiveSession,
  getLatestMessages,
  getPreviousMessages,
  getSession,
  hasMoreLocalMessages,
  listSessions,
  MESSAGES_PAGE_SIZE,
  renameSession,
  setActiveSessionId,
  updateSession,
  type ChatMessage,
  type ChatSession,
} from "@/features/agents/lib/chat-sessions";
import { mergeServerChatSessions, fetchServerSessionIntoLocal } from "@/features/agents/lib/chat-sessions-server";
import { api } from "@/lib/api";
import { useConfirmAction } from "@/hooks/use-confirm-action";

type Params = {
  selectedAgent: string;
  setSelectedAgent: (id: string) => void;
  agentFromUrl: string | null;
  convFromUrl: string | null;
  router: AppRouterInstance;
  listDefaultAgentId?: string;
  syncUrl: (agentId: string, convId?: string) => void;
};

export function useAgentsChatSessionSync({
  selectedAgent,
  setSelectedAgent,
  agentFromUrl,
  convFromUrl,
  router,
  listDefaultAgentId,
  syncUrl,
}: Params) {
  const [conversationId, setConversationId] = useState("");
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionTitle, setSessionTitle] = useState("新对话");
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const refreshSessions = useCallback((agentId: string) => {
    setSessions(listSessions(agentId));
  }, []);

  const loadSessionIntoUi = useCallback(
    (agentId: string, sessionId: string, clearComposer?: () => void) => {
      const session = getSession(agentId, sessionId);
      if (!session) return;
      setConversationId(session.id);
      const latest = getLatestMessages(session);
      setMessages(latest);
      setSessionTitle(session.title);
      setHasMore(session.messages.length > latest.length || (session.messageCount ?? 0) > session.messages.length);
      clearComposer?.();
    },
    [],
  );

  /** 向上滚动加载更早的消息。先从本地取，本地取完再请求服务端。 */
  const loadMoreMessages = useCallback(async () => {
    if (!selectedAgent || !conversationId) return;
    if (loadingMore) return;
    setLoadingMore(true);
    try {
      const session = getSession(selectedAgent, conversationId);
      if (!session) return;

      // 1) 先从本地缓存加载
      setMessages((prev) => {
        if (hasMoreLocalMessages(session, prev.length)) {
          const older = getPreviousMessages(session, prev.length);
          if (older.length > 0) {
            const newTotal = prev.length + older.length;
            setHasMore(hasMoreLocalMessages(session, newTotal)
              || (session.messageCount ?? 0) > newTotal);
            return [...older, ...prev];
          }
        }
        return prev;
      });

      // 2) 本地已空，从服务端拉取
      setMessages((prev) => {
        const oldestInUi = prev[0];
        const beforeSortIndex = oldestInUi?.sortIndex;
        if (beforeSortIndex == null) {
          setHasMore(false);
          return prev;
        }

        // 发起异步请求
        void (async () => {
          try {
            const detail = await api.getAgentChatSession(selectedAgent, conversationId, {
              before_sort_index: beforeSortIndex,
              limit: MESSAGES_PAGE_SIZE,
            });
            const serverMsgs: ChatMessage[] = detail.messages.map((m) => ({
              role: m.role as "user" | "assistant",
              content: m.content,
              sortIndex: m.sort_index,
              ...(m.media?.length ? { media: m.media as ChatMessage["media"] } : {}),
              ...(m.artifacts?.length ? { artifacts: m.artifacts as ChatMessage["artifacts"] } : {}),
              ...(m.steps?.length ? { steps: m.steps as Record<string, unknown>[] } : {}),
              ...(m.trace_id ? { traceId: m.trace_id } : {}),
            }));
            if (serverMsgs.length > 0) {
              // 合并到 localStorage
              const existing = getSession(selectedAgent, conversationId);
              if (existing) {
                const existingKeys = new Set(existing.messages.map((m) => `${m.role}|${m.content?.slice(0, 80)}`));
                const newOnly = serverMsgs.filter((m) => !existingKeys.has(`${m.role}|${m.content?.slice(0, 80)}`));
                if (newOnly.length > 0) {
                  const merged = [...newOnly, ...existing.messages];
                  updateSession(selectedAgent, conversationId, { messages: merged });
                }
              }
              setMessages((p) => [...serverMsgs, ...p]);
              setHasMore(detail.has_more ?? false);
            } else {
              setHasMore(false);
            }
          } catch {
            setHasMore(false);
          } finally {
            setLoadingMore(false);
          }
        })();
        return prev;
      });
    } catch {
      setLoadingMore(false);
    }
  }, [selectedAgent, conversationId, loadingMore]);

  useEffect(() => {
    if (agentFromUrl) setSelectedAgent(agentFromUrl);
  }, [agentFromUrl, setSelectedAgent]);

  useEffect(() => {
    if (!selectedAgent && listDefaultAgentId) {
      setSelectedAgent(listDefaultAgentId);
    }
  }, [listDefaultAgentId, selectedAgent, setSelectedAgent]);

  useEffect(() => {
    if (!selectedAgent) return;
    let cancelled = false;
    void (async () => {
      try {
        await mergeServerChatSessions(selectedAgent);
        if (!cancelled) refreshSessions(selectedAgent);
      } catch {
        /* 离线时仍用本地会话 */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshSessions, selectedAgent]);

  useEffect(() => {
    if (!selectedAgent) return;
    refreshSessions(selectedAgent);

    let session: ChatSession | null = null;
    if (convFromUrl) {
      session = getSession(selectedAgent, convFromUrl);
      if (session) setActiveSessionId(selectedAgent, convFromUrl);
    }
    if (!session) {
      session = ensureActiveSession(selectedAgent);
    }
    loadSessionIntoUi(selectedAgent, session.id);
    syncUrl(selectedAgent, session.id);
  }, [selectedAgent, convFromUrl, refreshSessions, loadSessionIntoUi, syncUrl]);

  const handleNewSession = useCallback(
    (clearComposer?: () => void) => {
      if (!selectedAgent) return;
      const session = createSession(selectedAgent);
      refreshSessions(selectedAgent);
      loadSessionIntoUi(selectedAgent, session.id, clearComposer);
      syncUrl(selectedAgent, session.id);
    },
    [loadSessionIntoUi, refreshSessions, selectedAgent, syncUrl],
  );

  const handleSelectSession = useCallback(
    (sessionId: string, onClosePanels: () => void, clearComposer?: () => void) => {
      if (!selectedAgent) return;
      setActiveSessionId(selectedAgent, sessionId);
      loadSessionIntoUi(selectedAgent, sessionId, clearComposer);
      syncUrl(selectedAgent, sessionId);
      onClosePanels();
    },
    [loadSessionIntoUi, selectedAgent, syncUrl],
  );

  const handleRenameSession = useCallback(
    (sessionId: string, title: string) => {
      if (!selectedAgent) return;
      if (!renameSession(selectedAgent, sessionId, title)) return;
      void api.updateAgentChatSession(selectedAgent, sessionId, { title: title.trim() }).catch(() => undefined);
      refreshSessions(selectedAgent);
      if (sessionId === conversationId) {
        const updated = getSession(selectedAgent, sessionId);
        if (updated) setSessionTitle(updated.title);
      }
    },
    [conversationId, refreshSessions, selectedAgent],
  );

  const handleDeleteSession = useCallback(
    (sessionId: string) => {
      if (!selectedAgent) return;
      requestConfirm({
        title: "删除会话",
        description: "此操作不可撤销。",
        message: "确定删除该会话？服务端与本地消息记录将无法恢复。",
        destructive: true,
        confirmLabel: "确认删除",
        onConfirm: async () => {
          await api.deleteAgentChatSession(selectedAgent, sessionId).catch(() => undefined);
          deleteSession(selectedAgent, sessionId);
          refreshSessions(selectedAgent);
          const next = ensureActiveSession(selectedAgent);
          loadSessionIntoUi(selectedAgent, next.id);
          syncUrl(selectedAgent, next.id);
        },
      });
    },
    [loadSessionIntoUi, refreshSessions, requestConfirm, selectedAgent, syncUrl],
  );

  const handleOpenTraceFromRecord = useCallback(
    async (sessionId: string) => {
      if (!selectedAgent) return;
      await fetchServerSessionIntoLocal(selectedAgent, sessionId);
      refreshSessions(selectedAgent);
      setActiveSessionId(selectedAgent, sessionId);
      loadSessionIntoUi(selectedAgent, sessionId);
      syncUrl(selectedAgent, sessionId);
    },
    [loadSessionIntoUi, refreshSessions, selectedAgent, syncUrl],
  );

  const onSelectAgent = useCallback(
    (id: string, onClosePanel: () => void) => {
      setSelectedAgent(id);
      onClosePanel();
      const params = new URLSearchParams();
      params.set("agent", id);
      router.replace(`/workbench/agents/chat?${params.toString()}`);
    },
    [router, setSelectedAgent],
  );

  return {
    conversationId,
    sessions,
    messages,
    setMessages,
    sessionTitle,
    setSessionTitle,
    refreshSessions,
    loadMoreMessages,
    loadingMore,
    hasMore,
    handleNewSession,
    handleSelectSession,
    handleRenameSession,
    handleDeleteSession,
    handleOpenTraceFromRecord,
    onSelectAgent,
    confirmDialog,
  };
}

export type AgentsChatSessionSync = ReturnType<typeof useAgentsChatSessionSync>;
