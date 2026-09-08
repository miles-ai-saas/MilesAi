"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useTraceTurnSelection } from "@/features/agents/hooks/use-agent-trace-turn-selection";
import { agentCarryForwardMediaEnabled, lastUserMessageMedia } from "@/features/agents/lib/chat-media-forward";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { useInfiniteList } from "@/hooks/use-infinite-list";
import { useAgentsChatLayout } from "@/features/agents/hooks/use-agents-chat-layout";
import { useAgentsChatMessaging } from "@/features/agents/hooks/use-agents-chat-messaging";
import { useAgentsChatRoute } from "@/features/agents/hooks/use-agents-chat-route";
import { useAgentsChatSession } from "@/features/agents/hooks/use-agents-chat-session";
import type { Agent } from "@/lib/types";

export function useAgentsChatPage() {
  const { ready } = useRequireAuth();
  const route = useAgentsChatRoute();
  const selectedAgent = route.agentId;

  const [imageN, setImageN] = useState(1);
  const [videoDuration, setVideoDuration] = useState(5);
  const [agentDetail, setAgentDetail] = useState<Agent | null>(null);

  const list = useInfiniteList(
    useCallback((p, s) => api.listAgents(p, s), []),
    {
      enabled: ready,
      pageSize: 30,
    },
  );

  const listedSelected = useMemo(() => list.items.find((a) => a.id === selectedAgent) ?? null, [list.items, selectedAgent]);

  useEffect(() => {
    if (!ready || !selectedAgent) {
      setAgentDetail(null);
      return;
    }
    if (listedSelected) {
      setAgentDetail(listedSelected);
      return;
    }
    let cancelled = false;
    void api
      .getAgent(selectedAgent)
      .then((agent) => {
        if (!cancelled) setAgentDetail(agent);
      })
      .catch(() => {
        if (!cancelled) setAgentDetail(null);
      });
    return () => {
      cancelled = true;
    };
  }, [ready, selectedAgent, listedSelected]);

  const session = useAgentsChatSession(selectedAgent, route.conversationId, {
    selectAgent: route.selectAgent,
    selectConversation: route.selectConversation,
    clearConversation: route.clearConversation,
  });

  const { selectedTurnIndex, setSelectedTurnIndex } = useTraceTurnSelection(session.messages, session.conversationId);

  const layout = useAgentsChatLayout({
    tabFromUrl: route.tab,
    messages: session.messages,
    replaceQuery: route.replaceQuery,
    setSelectedTurnIndex,
  });

  const selected = listedSelected ?? agentDetail;
  const carryForwardMedia = agentCarryForwardMediaEnabled(selected?.config);

  const toolSlugs: string[] = useMemo(() => {
    const slugs = selected?.config?.tool_slugs;
    if (Array.isArray(slugs)) return slugs.map(String);
    return [];
  }, [selected?.config?.tool_slugs]);
  // 生图/生视频由 enable_generative_tools 挂载，不一定写入 tool_slugs
  const hasGenerativeTools = Boolean(selected?.config?.enable_generative_tools);
  const hasImageTool = hasGenerativeTools || toolSlugs.includes("generate_image");
  const hasVideoTool = hasGenerativeTools || toolSlugs.includes("generate_video");

  const messaging = useAgentsChatMessaging({
    selectedAgent,
    conversationId: session.conversationId,
    messages: session.messages,
    setMessages: session.setMessages,
    setSessionTitle: session.setSessionTitle,
    refreshSessions: session.refreshSessions,
    ensureConversation: session.ensureConversation,
    carryForwardMedia,
    initialPrompt: route.prompt,
    generativeImageN: imageN,
    generativeVideoDuration: videoDuration,
  });

  const carriedMedia = useMemo(() => {
    if (messaging.pendingMedia.length > 0 || !carryForwardMedia) return [];
    return lastUserMessageMedia(session.messages);
  }, [carryForwardMedia, messaging.pendingMedia.length, session.messages]);

  const lastTraceId = useMemo(() => {
    for (let i = session.messages.length - 1; i >= 0; i -= 1) {
      const m = session.messages[i];
      if (m.role === "assistant" && m.traceId) return m.traceId;
    }
    return null;
  }, [session.messages]);

  const handleAgentRenamed = useCallback(() => {
    void list.reload();
    if (!selectedAgent) return;
    void api
      .getAgent(selectedAgent)
      .then(setAgentDetail)
      .catch(() => undefined);
  }, [list, selectedAgent]);

  const leftSidebarProps = {
    agents: list.items,
    total: list.total,
    selectedAgentId: selectedAgent,
    sessions: session.sessions,
    activeSessionId: session.conversationId || null,
    collapsed: layout.leftCollapsed,
    agentsColumnCompact: layout.agentsColumnCompact,
    hasMoreAgents: list.hasMore,
    loadingMoreAgents: list.loadingMore,
    onLoadMoreAgents: () => void list.loadMore(),
    onSelectAgent: (id: string) => session.onSelectAgent(id, () => layout.setPanelOpen(false)),
    onNewSession: () => session.handleNewSession(messaging.clearComposer),
    onSelectSession: (sessionId: string) => session.handleSelectSession(sessionId, layout.closeTransientPanels, messaging.clearComposer),
    onRenameSession: session.handleRenameSession,
    onDeleteSession: session.handleDeleteSession,
  };

  const effectiveApiError = messaging.apiError || session.sessionError;
  const effectiveClearApiError = useCallback(() => {
    messaging.clearApiError();
    session.clearSessionError();
  }, [messaging, session]);

  return {
    ready,
    list,
    selectedAgent,
    conversationId: session.conversationId,
    sessions: session.sessions,
    messages: session.messages,
    sessionTitle: session.sessionTitle,
    workbenchTab: layout.workbenchTab,
    panelOpen: layout.panelOpen,
    leftCollapsed: layout.leftCollapsed,
    rightCollapsed: layout.rightCollapsed,
    agentsColumnCompact: layout.agentsColumnCompact,
    focusMode: layout.focusMode,
    leftDrawerOpen: layout.leftDrawerOpen,
    setLeftDrawerOpen: layout.setLeftDrawerOpen,
    query: messaging.query,
    setQuery: messaging.setQuery,
    imageN,
    setImageN,
    videoDuration,
    setVideoDuration,
    hasImageTool,
    hasVideoTool,
    pendingMedia: messaging.pendingMedia,
    uploadingMedia: messaging.uploadingMedia,
    chatting: messaging.chatting,
    pendingTool: messaging.pendingTool,
    wsEnabled: messaging.wsEnabled,
    wsReady: messaging.wsReady,
    selected,
    carryForwardMedia,
    carriedMedia,
    chattingStatusLabel: messaging.chattingStatusLabel,
    lastTraceId,
    generativeStatusEl: messaging.generativeStatusEl,
    cancelGenerativeJobById: messaging.cancelGenerativeJobById,
    onGenerativeJobRetried: messaging.onGenerativeJobRetried,
    apiError: effectiveApiError,
    clearApiError: effectiveClearApiError,
    loadMoreMessages: session.loadMoreMessages,
    loadingMore: session.loadingMore,
    hasMore: session.hasMore,
    leftSidebarProps,
    selectedTurnIndex,
    setSelectedTurnIndex,
    confirmDialog: session.confirmDialog,
    persistSidebar: layout.persistSidebar,
    setLeftCollapsed: layout.setLeftCollapsed,
    setRightCollapsed: layout.setRightCollapsed,
    setAgentsColumnCompact: layout.setAgentsColumnCompact,
    setFocusMode: layout.setFocusMode,
    setPanelOpen: layout.setPanelOpen,
    onTabChange: layout.onTabChange,
    handleNewSession: () => session.handleNewSession(messaging.clearComposer),
    handleRenameSession: session.handleRenameSession,
    openTraceLatest: layout.openTraceLatest,
    openTraceAtTurn: layout.openTraceAtTurn,
    handleOpenTraceFromRecord: session.handleOpenTraceFromRecord,
    closePanel: layout.closePanel,
    chat: messaging.chat,
    confirmPendingTool: messaging.confirmPendingTool,
    onPickAttachments: messaging.onPickAttachments,
    removePendingMedia: messaging.removePendingMedia,
    handleAgentRenamed,
  };
}

export type AgentsChatPageVm = ReturnType<typeof useAgentsChatPage>;
