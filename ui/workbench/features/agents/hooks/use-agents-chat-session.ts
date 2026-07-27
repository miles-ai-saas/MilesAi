"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  createSession,
  deleteSession,
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
import { fetchServerSessionIntoLocal, mapServerMessages, mergeMessages, mergeServerChatSessions } from "@/features/agents/lib/chat-sessions-server";
import { reconcileInFlightGenerativeArtifacts } from "@/features/agents/lib/reconcile-generative-artifacts";
import { api } from "@/lib/api";
import { useConfirmAction } from "@/hooks/use-confirm-action";

type RouteActions = {
  selectAgent: (id: string) => void;
  selectConversation: (convId: string) => void;
  clearConversation: () => void;
};

/**
 * 会话列表与消息：由 URL 上的 agentId / conversationId 驱动。
 * 不写 URL、不做智能体兜底；选中/新建/删除通过 route 回写。
 */
export function useAgentsChatSession(
  agentId: string,
  conversationIdFromUrl: string,
  route: RouteActions,
) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [conversationId, setConversationId] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionTitle, setSessionTitle] = useState("新对话");
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const routeRef = useRef(route);
  routeRef.current = route;

  const clearConversationUi = useCallback(() => {
    setConversationId("");
    setMessages([]);
    setSessionTitle("新对话");
    setHasMore(false);
  }, []);

  const refreshSessions = useCallback((id: string) => {
    setSessions(id ? listSessions(id) : []);
  }, []);

  const applySessionToUi = useCallback((agent: string, sessionId: string, clearComposer?: () => void) => {
    const session = getSession(agent, sessionId);
    if (!session) return false;
    setConversationId(session.id);
    const latest = getLatestMessages(session);
    setMessages(latest);
    setSessionTitle(session.title);
    setHasMore(session.messages.length > latest.length || (session.messageCount ?? 0) > session.messages.length);
    clearComposer?.();
    return true;
  }, []);

  /** 打开会话：先拉服务端（hydrate），再展示，再 reconcile 终态任务，避免刷新后仍显示排队中。 */
  const openSession = useCallback(
    async (agent: string, sessionId: string, clearComposer?: () => void, isCancelled?: () => boolean) => {
      setActiveSessionId(agent, sessionId);
      applySessionToUi(agent, sessionId, clearComposer);
      await fetchServerSessionIntoLocal(agent, sessionId);
      if (isCancelled?.()) return;
      const session = getSession(agent, sessionId);
      if (!session) {
        if (!isCancelled?.()) clearConversationUi();
        return;
      }
      setConversationId(session.id);
      setSessionTitle(session.title);
      const latest = getLatestMessages(session);
      setHasMore(session.messages.length > latest.length || (session.messageCount ?? 0) > session.messages.length);
      setMessages(latest);
      refreshSessions(agent);
      const reconciled = await reconcileInFlightGenerativeArtifacts(agent, sessionId, latest);
      if (isCancelled?.()) return;
      setMessages(reconciled);
    },
    [applySessionToUi, clearConversationUi, refreshSessions],
  );

  // agent 变化：刷新列表并后台合并
  useEffect(() => {
    if (!agentId) {
      setSessions([]);
      clearConversationUi();
      return;
    }
    refreshSessions(agentId);
    let cancelled = false;
    void (async () => {
      try {
        await mergeServerChatSessions(agentId);
        if (!cancelled) refreshSessions(agentId);
      } catch {
        /* 离线用本地 */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [agentId, refreshSessions, clearConversationUi]);

  // conv 是打开会话的唯一信号
  useEffect(() => {
    if (!agentId || !conversationIdFromUrl) {
      clearConversationUi();
      return;
    }
    let cancelled = false;
    void openSession(agentId, conversationIdFromUrl, undefined, () => cancelled);
    return () => {
      cancelled = true;
    };
  }, [agentId, conversationIdFromUrl, openSession, clearConversationUi]);

  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  const loadMoreMessages = useCallback(async () => {
    if (!agentId || !conversationId || loadingMore) return;
    setLoadingMore(true);
    try {
      const session = getSession(agentId, conversationId);
      if (!session) {
        setHasMore(false);
        return;
      }
      const current = messagesRef.current;
      if (hasMoreLocalMessages(session, current.length)) {
        const older = getPreviousMessages(session, current.length);
        if (older.length > 0) {
          const newTotal = current.length + older.length;
          setMessages((prev) => [...older, ...prev]);
          setHasMore(hasMoreLocalMessages(session, newTotal) || (session.messageCount ?? 0) > newTotal);
          return;
        }
      }
      const oldestInUi = current[0];
      const beforeSortIndex = oldestInUi?.sortIndex;
      if (beforeSortIndex == null) {
        setHasMore(false);
        return;
      }
      const detail = await api.getAgentChatSession(agentId, conversationId, {
        before_sort_index: beforeSortIndex,
        limit: MESSAGES_PAGE_SIZE,
      });
      const serverMsgs = mapServerMessages(detail.messages);
      if (serverMsgs.length > 0) {
        const existing = getSession(agentId, conversationId);
        if (existing) {
          updateSession(agentId, conversationId, { messages: mergeMessages(existing.messages, serverMsgs) });
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
  }, [agentId, conversationId, loadingMore]);

  const handleNewSession = useCallback(
    (clearComposer?: () => void) => {
      if (!agentId) return;
      const session = createSession(agentId);
      void api.createAgentChatSession(agentId, { id: session.id, title: session.title }).catch((e) => {
        setSessionError(e instanceof Error ? e.message : "会话创建同步失败");
      });
      refreshSessions(agentId);
      applySessionToUi(agentId, session.id, clearComposer);
      routeRef.current.selectConversation(session.id);
    },
    [agentId, applySessionToUi, refreshSessions],
  );

  const handleSelectSession = useCallback(
    (sessionId: string, onClosePanels: () => void, clearComposer?: () => void) => {
      if (!agentId) return;
      onClosePanels();
      routeRef.current.selectConversation(sessionId);
      void openSession(agentId, sessionId, clearComposer);
    },
    [agentId, openSession],
  );

  const handleRenameSession = useCallback(
    (sessionId: string, title: string) => {
      if (!agentId) return;
      if (!renameSession(agentId, sessionId, title)) return;
      void api.updateAgentChatSession(agentId, sessionId, { title: title.trim() }).catch((e) => {
        setSessionError(e instanceof Error ? e.message : "重命名同步失败");
      });
      refreshSessions(agentId);
      if (sessionId === conversationId) {
        const updated = getSession(agentId, sessionId);
        if (updated) setSessionTitle(updated.title);
      }
    },
    [agentId, conversationId, refreshSessions],
  );

  const handleDeleteSession = useCallback(
    (sessionId: string) => {
      if (!agentId) return;
      requestConfirm({
        title: "删除会话",
        description: "此操作不可撤销。",
        message: "确定删除该会话？服务端与本地消息记录将无法恢复。",
        destructive: true,
        confirmLabel: "确认删除",
        onConfirm: async () => {
          await api.deleteAgentChatSession(agentId, sessionId).catch((e) => {
            setSessionError(e instanceof Error ? e.message : "删除会话同步失败");
          });
          deleteSession(agentId, sessionId);
          refreshSessions(agentId);
          if (sessionId === conversationId || sessionId === conversationIdFromUrl) {
            clearConversationUi();
            routeRef.current.clearConversation();
          }
        },
      });
    },
    [agentId, clearConversationUi, conversationId, conversationIdFromUrl, refreshSessions, requestConfirm],
  );

  const handleOpenTraceFromRecord = useCallback(
    (sessionId: string) => {
      if (!agentId) return;
      routeRef.current.selectConversation(sessionId);
      void openSession(agentId, sessionId);
    },
    [agentId, openSession],
  );

  const onSelectAgent = useCallback((id: string, onClosePanel: () => void) => {
    onClosePanel();
    routeRef.current.selectAgent(id);
  }, []);

  return {
    conversationId,
    sessions,
    messages,
    setMessages,
    sessionTitle,
    setSessionTitle,
    refreshSessions: () => {
      if (agentId) refreshSessions(agentId);
    },
    loadMoreMessages,
    loadingMore,
    hasMore,
    sessionError,
    clearSessionError: () => setSessionError(null),
    handleNewSession,
    handleSelectSession,
    handleRenameSession,
    handleDeleteSession,
    handleOpenTraceFromRecord,
    onSelectAgent,
    confirmDialog,
  };
}

export type AgentsChatSession = ReturnType<typeof useAgentsChatSession>;
