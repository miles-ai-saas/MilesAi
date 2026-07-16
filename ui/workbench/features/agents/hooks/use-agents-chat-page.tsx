"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTraceTurnSelection } from "@/features/agents/hooks/use-agent-trace-turn-selection";
import { agentCarryForwardMediaEnabled, lastUserMessageMedia } from "@/features/agents/lib/chat-media-forward";
import { loadBusinessContext, type BusinessContext } from "@/features/projects";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { useInfiniteList } from "@/hooks/use-infinite-list";
import { useAgentsChatLayout } from "@/features/agents/hooks/use-agents-chat-layout";
import { useAgentsChatMessaging } from "@/features/agents/hooks/use-agents-chat-messaging";
import { useAgentsChatSessionSync } from "@/features/agents/hooks/use-agents-chat-session-sync";

export function useAgentsChatPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const agentFromUrl = searchParams.get("agent");
  const convFromUrl = searchParams.get("conv");
  const tabFromUrl = searchParams.get("tab");
  const promptFromUrl = searchParams.get("prompt");
  const bizFromUrl = searchParams.get("biz");
  const { ready } = useRequireAuth();

  const [businessContext, setBusinessContext] = useState<BusinessContext | null>(null);
  const [imageN, setImageN] = useState(1);
  const [videoDuration, setVideoDuration] = useState(5);

  useEffect(() => {
    if (bizFromUrl === "1" || searchParams.get("projectId")) {
      setBusinessContext(loadBusinessContext());
    }
  }, [bizFromUrl, searchParams]);

  const [selectedAgent, setSelectedAgent] = useState<string>(agentFromUrl ?? "");

  const list = useInfiniteList(useCallback((p, s) => api.listAgents(p, s), []), {
    enabled: ready,
    pageSize: 30,
  });

  const syncUrl = useCallback(
    (agentId: string, convId?: string) => {
      const params = new URLSearchParams();
      params.set("agent", agentId);
      if (convId) params.set("conv", convId);
      const projectId = searchParams.get("projectId");
      const wpId = searchParams.get("wpId");
      if (projectId) params.set("projectId", projectId);
      if (wpId) params.set("wpId", wpId);
      if (bizFromUrl === "1") params.set("biz", "1");
      router.replace(`/workbench/agents/chat?${params.toString()}`);
    },
    [router, searchParams, bizFromUrl],
  );

  const session = useAgentsChatSessionSync({
    selectedAgent,
    setSelectedAgent,
    agentFromUrl,
    convFromUrl,
    router,
    listDefaultAgentId: list.items[0]?.id,
    syncUrl,
  });

  const { selectedTurnIndex, setSelectedTurnIndex } = useTraceTurnSelection(session.messages, session.conversationId);

  const layout = useAgentsChatLayout({
    tabFromUrl,
    selectedAgent,
    conversationId: session.conversationId,
    messages: session.messages,
    router,
    setSelectedTurnIndex,
  });

  const selected = list.items.find((a) => a.id === selectedAgent);
  const carryForwardMedia = agentCarryForwardMediaEnabled(selected?.config);

  const toolSlugs: string[] = useMemo(() => {
    const slugs = selected?.config?.tool_slugs;
    if (Array.isArray(slugs)) return slugs.map(String);
    return [];
  }, [selected?.config?.tool_slugs]);
  const hasImageTool = toolSlugs.includes("generate_image");
  const hasVideoTool = toolSlugs.includes("generate_video");

  const messaging = useAgentsChatMessaging({
    selectedAgent,
    conversationId: session.conversationId,
    messages: session.messages,
    setMessages: session.setMessages,
    setSessionTitle: session.setSessionTitle,
    refreshSessions: session.refreshSessions,
    carryForwardMedia,
    businessContext,
    initialPrompt: promptFromUrl,
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
  }, [list]);

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
    businessContext,
    clearBusinessContext: () => setBusinessContext(null),
  };
}

export type AgentsChatPageVm = ReturnType<typeof useAgentsChatPage>;
