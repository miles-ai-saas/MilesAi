"use client";

import { useCallback, useEffect, useState } from "react";
import { defaultTraceTurnIndex, listTraceTurns } from "@/features/agents/lib/agent-trace";
import type { AgentsChatQuery } from "@/features/agents/lib/agents-chat-href";
import type { ChatMessage } from "@/features/agents/lib/chat-sessions";

export type AgentWorkbenchTab = "config" | "trace" | "schedule" | "architecture" | "api" | "call_records" | "stats";

export const AGENT_WORKBENCH_TABS: {
  id: AgentWorkbenchTab;
  label: string;
  ready: boolean;
}[] = [
  { id: "config", label: "配置", ready: true },
  { id: "trace", label: "Trace", ready: true },
  { id: "schedule", label: "定时", ready: true },
  { id: "architecture", label: "架构", ready: true },
  { id: "api", label: "API", ready: true },
  { id: "call_records", label: "调用记录", ready: true },
  { id: "stats", label: "统计", ready: true },
];

export function normalizeAgentWorkbenchTab(value: string | null): AgentWorkbenchTab | null {
  if (!value) return null;
  return AGENT_WORKBENCH_TABS.some((t) => t.id === value) ? (value as AgentWorkbenchTab) : null;
}

export function isAgentWorkbenchTab(value: string | null): value is AgentWorkbenchTab {
  return normalizeAgentWorkbenchTab(value) != null;
}

export const CHAT_AGENT_COLUMN = "11rem";
export const CHAT_AGENT_COLUMN_COMPACT = "3rem";
export const CHAT_SESSION_COLUMN = "13rem";
export const CHAT_LEFT_SIDEBAR_EXPANDED = "24rem";
export const CHAT_LEFT_SIDEBAR_COLLAPSED = "3rem";
export const CHAT_RIGHT_RAIL_EXPANDED = "11.5rem";
export const CHAT_RIGHT_RAIL_COLLAPSED = "3rem";

export const CHAT_SIDEBAR_STORAGE_KEY = "agents-chat-sidebar";

export type ChatSidebarPrefs = {
  leftCollapsed?: boolean;
  rightCollapsed?: boolean;
  agentsColumnCompact?: boolean;
  focusMode?: boolean;
};

export function loadChatSidebarPrefs(): ChatSidebarPrefs {
  if (typeof window === "undefined") return {};
  try {
    const raw = localStorage.getItem(CHAT_SIDEBAR_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as ChatSidebarPrefs & { leftTab?: string };
    return {
      leftCollapsed: parsed.leftCollapsed,
      rightCollapsed: parsed.rightCollapsed,
      agentsColumnCompact: parsed.agentsColumnCompact,
      focusMode: parsed.focusMode,
    };
  } catch {
    return {};
  }
}

export function saveChatSidebarPrefs(prefs: ChatSidebarPrefs) {
  try {
    localStorage.setItem(CHAT_SIDEBAR_STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    /* ignore */
  }
}

type Params = {
  tabFromUrl: string | null;
  messages: ChatMessage[];
  replaceQuery: (patch: AgentsChatQuery) => void;
  setSelectedTurnIndex: (index: number) => void;
};

export function useAgentsChatLayout({
  tabFromUrl,
  messages,
  replaceQuery,
  setSelectedTurnIndex,
}: Params) {
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
      // 只改 tab，保留地址栏现有 agent/conv
      replaceQuery({
        tab: tab !== "config" ? tab : null,
      });
    },
    [replaceQuery],
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
    replaceQuery({ tab: null });
  }, [replaceQuery]);

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
