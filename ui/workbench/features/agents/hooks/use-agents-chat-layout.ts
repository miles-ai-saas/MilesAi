"use client";

import { useCallback, useEffect, useState } from "react";
import type { AppRouterInstance } from "next/dist/shared/lib/app-router-context.shared-runtime";
import { normalizeAgentWorkbenchTab, type AgentWorkbenchTab } from "@/features/agents/components/agent-workbench-tabs";
import { loadChatSidebarPrefs, saveChatSidebarPrefs, type ChatSidebarPrefs } from "@/features/agents/components/chat-sidebar-layout";
import { defaultTraceTurnIndex, listTraceTurns } from "@/features/agents/lib/agent-trace";
import type { ChatMessage } from "@/features/agents/lib/chat-sessions";

type Params = {
  tabFromUrl: string | null;
  selectedAgent: string;
  conversationId: string;
  messages: ChatMessage[];
  router: AppRouterInstance;
  setSelectedTurnIndex: (index: number) => void;
};

export function useAgentsChatLayout({ tabFromUrl, selectedAgent, conversationId, messages, router, setSelectedTurnIndex }: Params) {
  const [workbenchTab, setWorkbenchTab] = useState<AgentWorkbenchTab>("config");
  const [panelOpen, setPanelOpen] = useState(false);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [agentsColumnCompact, setAgentsColumnCompact] = useState(true);
  const [focusMode, setFocusMode] = useState(false);
  const [leftDrawerOpen, setLeftDrawerOpen] = useState(false);

  useEffect(() => {
    const prefs = loadChatSidebarPrefs();
    if (prefs.leftCollapsed) setLeftCollapsed(true);
    if (prefs.rightCollapsed) setRightCollapsed(true);
    if (prefs.agentsColumnCompact === false) setAgentsColumnCompact(false);
    if (prefs.focusMode) setFocusMode(true);
  }, []);

  useEffect(() => {
    const tab = normalizeAgentWorkbenchTab(tabFromUrl);
    if (tab) {
      setWorkbenchTab(tab);
      setPanelOpen(true);
    }
  }, [tabFromUrl]);

  const persistSidebar = useCallback(
    (patch: Partial<ChatSidebarPrefs>) => {
      saveChatSidebarPrefs({
        leftCollapsed: patch.leftCollapsed ?? leftCollapsed,
        rightCollapsed: patch.rightCollapsed ?? rightCollapsed,
        agentsColumnCompact: patch.agentsColumnCompact ?? agentsColumnCompact,
        focusMode: patch.focusMode ?? focusMode,
      });
    },
    [agentsColumnCompact, focusMode, leftCollapsed, rightCollapsed],
  );

  const onTabChange = useCallback(
    (tab: AgentWorkbenchTab) => {
      setWorkbenchTab(tab);
      setPanelOpen(true);
      const params = new URLSearchParams();
      if (selectedAgent) params.set("agent", selectedAgent);
      if (conversationId) params.set("conv", conversationId);
      if (tab !== "config") params.set("tab", tab);
      router.replace(`/workbench/agents/chat?${params.toString()}`);
    },
    [conversationId, router, selectedAgent],
  );

  const openTraceAtTurn = useCallback(
    (turnIndex: number) => {
      setSelectedTurnIndex(turnIndex);
      onTabChange("trace");
    },
    [onTabChange, setSelectedTurnIndex],
  );

  const openTraceLatest = useCallback(() => {
    const turns = listTraceTurns(messages);
    setSelectedTurnIndex(defaultTraceTurnIndex(turns));
    onTabChange("trace");
  }, [messages, onTabChange, setSelectedTurnIndex]);

  const closePanel = useCallback(() => {
    setPanelOpen(false);
    const params = new URLSearchParams();
    if (selectedAgent) params.set("agent", selectedAgent);
    if (conversationId) params.set("conv", conversationId);
    router.replace(`/workbench/agents/chat?${params.toString()}`);
  }, [conversationId, router, selectedAgent]);

  const closeTransientPanels = useCallback(() => {
    setPanelOpen(false);
    setLeftDrawerOpen(false);
  }, []);

  return {
    workbenchTab,
    panelOpen,
    leftCollapsed,
    rightCollapsed,
    agentsColumnCompact,
    focusMode,
    leftDrawerOpen,
    setLeftDrawerOpen,
    persistSidebar,
    setLeftCollapsed,
    setRightCollapsed,
    setAgentsColumnCompact,
    setFocusMode,
    setPanelOpen,
    onTabChange,
    openTraceAtTurn,
    openTraceLatest,
    closePanel,
    closeTransientPanels,
  };
}

export type AgentsChatLayout = ReturnType<typeof useAgentsChatLayout>;
