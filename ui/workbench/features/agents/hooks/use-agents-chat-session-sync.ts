"use client";

import { useCallback, useEffect, useState } from "react";
import type { AppRouterInstance } from "next/dist/shared/lib/app-router-context.shared-runtime";
import {
  createSession,
  deleteSession,
  ensureActiveSession,
  getSession,
  listSessions,
  renameSession,
  setActiveSessionId,
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
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const refreshSessions = useCallback((agentId: string) => {
    setSessions(listSessions(agentId));
  }, []);

  const loadSessionIntoUi = useCallback(
    (agentId: string, sessionId: string, clearComposer?: () => void) => {
      const session = getSession(agentId, sessionId);
      if (!session) return;
      setConversationId(session.id);
      setMessages([...session.messages]);
      setSessionTitle(session.title);
      clearComposer?.();
    },
    [],
  );

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
