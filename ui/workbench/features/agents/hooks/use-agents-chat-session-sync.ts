"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { AppRouterInstance } from "next/dist/shared/lib/app-router-context.shared-runtime";
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
import { loadLastAgentsChat, replaceAgentsChat } from "@/features/agents/lib/agents-chat-href";
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
  const [sessionError, setSessionError] = useState<string | null>(null);
  const { requestConfirm, confirmDialog } = useConfirmAction();
  const syncUrlRef = useRef(syncUrl);
  syncUrlRef.current = syncUrl;
  /** 每个 agent 只自动 bootstrap 一次，避免 merge/URL 写回触发重复建会话 */
  const bootstrappedAgentRef = useRef<string | null>(null);

  const refreshSessions = useCallback((agentId: string) => {
    setSessions(listSessions(agentId));
  }, []);

  const clearConversationUi = useCallback(() => {
    setConversationId("");
    setMessages([]);
    setSessionTitle("新对话");
    setHasMore(false);
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

      // 校正仍显示「排队中」但任务已成功的生图卡片
      void reconcileInFlightGenerativeArtifacts(agentId, sessionId, latest).then((reconciled) => {
        if (reconciled === latest) return;
        setConversationId((cid) => {
          if (cid === sessionId) setMessages(reconciled);
          return cid;
        });
      });
    },
    [],
  );

  /** 选中会话后：本地先展示，再拉服务端详情补齐。 */
  const openSession = useCallback(
    (agentId: string, sessionId: string, clearComposer?: () => void) => {
      setActiveSessionId(agentId, sessionId);
      loadSessionIntoUi(agentId, sessionId, clearComposer);
      void (async () => {
        await fetchServerSessionIntoLocal(agentId, sessionId);
        loadSessionIntoUi(agentId, sessionId);
        refreshSessions(agentId);
      })();
    },
    [loadSessionIntoUi, refreshSessions],
  );

  /** 向上滚动加载更早的消息。先从本地取，本地取完再请求服务端。 */
  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  const loadMoreMessages = useCallback(async () => {
    if (!selectedAgent || !conversationId) return;
    if (loadingMore) return;
    setLoadingMore(true);
    try {
      const session = getSession(selectedAgent, conversationId);
      if (!session) {
        setHasMore(false);
        return;
      }

      const current = messagesRef.current;

      // 1) 先从本地缓存加载
      if (hasMoreLocalMessages(session, current.length)) {
        const older = getPreviousMessages(session, current.length);
        if (older.length > 0) {
          const newTotal = current.length + older.length;
          setMessages((prev) => [...older, ...prev]);
          setHasMore(hasMoreLocalMessages(session, newTotal) || (session.messageCount ?? 0) > newTotal);
          return;
        }
      }

      // 2) 本地已空，从服务端拉取
      const oldestInUi = current[0];
      const beforeSortIndex = oldestInUi?.sortIndex;
      if (beforeSortIndex == null) {
        setHasMore(false);
        return;
      }

      const detail = await api.getAgentChatSession(selectedAgent, conversationId, {
        before_sort_index: beforeSortIndex,
        limit: MESSAGES_PAGE_SIZE,
      });
      const serverMsgs: ChatMessage[] = mapServerMessages(detail.messages);
      if (serverMsgs.length > 0) {
        const existing = getSession(selectedAgent, conversationId);
        if (existing) {
          const merged = mergeMessages(existing.messages, serverMsgs);
          updateSession(selectedAgent, conversationId, { messages: merged });
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
  }, [selectedAgent, conversationId, loadingMore]);

  useEffect(() => {
    if (agentFromUrl) {
      setSelectedAgent(agentFromUrl);
      return;
    }
    // 裸 /chat/：先用书签恢复，不依赖 listAgents
    const last = loadLastAgentsChat();
    if (last?.agentId) setSelectedAgent(last.agentId);
  }, [agentFromUrl, setSelectedAgent]);

  useEffect(() => {
    if (!selectedAgent && listDefaultAgentId) {
      setSelectedAgent(listDefaultAgentId);
    }
  }, [listDefaultAgentId, selectedAgent, setSelectedAgent]);

  // 选定 agent → 只同步 ?agent= 并拉会话列表；有 ?conv= 时才打开会话并查详情
  useEffect(() => {
    if (!selectedAgent) {
      bootstrappedAgentRef.current = null;
      clearConversationUi();
      return;
    }

    const isNewAgent = bootstrappedAgentRef.current !== selectedAgent;
    if (isNewAgent) {
      bootstrappedAgentRef.current = selectedAgent;
    }

    refreshSessions(selectedAgent);

    const search = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : null;
    const urlAgent = search?.get("agent") ?? "";
    const urlConv = search?.get("conv") ?? "";
    // 入口/切智能体：URL 只保证 agent；去掉不应出现的 conv
    const wantConv = convFromUrl || null;
    const urlNeedsSync = urlAgent !== selectedAgent || urlConv !== (wantConv ?? "");

    if (isNewAgent || urlNeedsSync) {
      syncUrlRef.current(selectedAgent, wantConv ?? undefined);
    }

    if (wantConv) {
      const local = getSession(selectedAgent, wantConv);
      if (local) {
        loadSessionIntoUi(selectedAgent, wantConv);
      } else {
        clearConversationUi();
      }
      void (async () => {
        await fetchServerSessionIntoLocal(selectedAgent, wantConv);
        loadSessionIntoUi(selectedAgent, wantConv);
        refreshSessions(selectedAgent);
      })();
    } else {
      clearConversationUi();
    }

    if (!isNewAgent) return;

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
  }, [selectedAgent, convFromUrl, refreshSessions, loadSessionIntoUi, clearConversationUi]);

  const handleNewSession = useCallback(
    (clearComposer?: () => void) => {
      if (!selectedAgent) return;
      const session = createSession(selectedAgent);
      void api.createAgentChatSession(selectedAgent, { id: session.id, title: session.title })
        .catch((e) => setSessionError(e instanceof Error ? e.message : "会话创建同步失败"));
      refreshSessions(selectedAgent);
      loadSessionIntoUi(selectedAgent, session.id, clearComposer);
      syncUrl(selectedAgent, session.id);
    },
    [loadSessionIntoUi, refreshSessions, selectedAgent, setSessionError, syncUrl],
  );

  const handleSelectSession = useCallback(
    (sessionId: string, onClosePanels: () => void, clearComposer?: () => void) => {
      if (!selectedAgent) return;
      syncUrl(selectedAgent, sessionId);
      onClosePanels();
      openSession(selectedAgent, sessionId, clearComposer);
    },
    [openSession, selectedAgent, syncUrl],
  );

  const handleRenameSession = useCallback(
    (sessionId: string, title: string) => {
      if (!selectedAgent) return;
      if (!renameSession(selectedAgent, sessionId, title)) return;
      void api.updateAgentChatSession(selectedAgent, sessionId, { title: title.trim() }).catch((e) => {
        setSessionError(e instanceof Error ? e.message : "重命名同步失败");
      });
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
          await api.deleteAgentChatSession(selectedAgent, sessionId).catch((e) => {
            setSessionError(e instanceof Error ? e.message : "删除会话同步失败");
          });
          deleteSession(selectedAgent, sessionId);
          refreshSessions(selectedAgent);
          if (sessionId === conversationId) {
            clearConversationUi();
            syncUrl(selectedAgent);
          }
        },
      });
    },
    [clearConversationUi, conversationId, refreshSessions, requestConfirm, selectedAgent, syncUrl],
  );

  const handleOpenTraceFromRecord = useCallback(
    async (sessionId: string) => {
      if (!selectedAgent) return;
      syncUrl(selectedAgent, sessionId);
      openSession(selectedAgent, sessionId);
    },
    [openSession, selectedAgent, syncUrl],
  );

  const onSelectAgent = useCallback(
    (id: string, onClosePanel: () => void) => {
      setSelectedAgent(id);
      onClosePanel();
      // 切智能体：只带 agent，清空会话选中
      replaceAgentsChat(router, { agent: id });
      clearConversationUi();
    },
    [clearConversationUi, router, setSelectedAgent],
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

export type AgentsChatSessionSync = ReturnType<typeof useAgentsChatSessionSync>;
