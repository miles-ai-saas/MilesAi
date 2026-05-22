"use client";

import { useEffect, useState } from "react";
import { AgentChatSessionPanel } from "@/components/agent/AgentChatSessionPanel";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import {
  CHAT_LEFT_SIDEBAR_COLLAPSED,
  CHAT_LEFT_SIDEBAR_EXPANDED,
} from "@/components/agent/chat-sidebar-layout";
import { SidebarCollapseButton } from "@/components/agent/SidebarCollapseButton";
import type { ChatSession } from "@/lib/chat-sessions";
import { agentModeLabel } from "@/lib/agent-utils";
import type { Agent } from "@/lib/types";

export type LeftSidebarTab = "agents" | "sessions";

type Props = {
  agents: Agent[];
  total: number;
  page: number;
  size: number;
  selectedAgentId: string;
  sessions: ChatSession[];
  activeSessionId: string | null;
  collapsed: boolean;
  defaultTab?: LeftSidebarTab;
  onToggleCollapse: () => void;
  onSelectAgent: (id: string) => void;
  onPageChange: (page: number) => void;
  onNewSession: () => void;
  onSelectSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
  onTabChange?: (tab: LeftSidebarTab) => void;
};

function agentInitial(name: string) {
  return (name.trim()[0] ?? "?").toUpperCase();
}

export function AgentChatLeftSidebar({
  agents,
  total,
  page,
  size,
  selectedAgentId,
  sessions,
  activeSessionId,
  collapsed,
  defaultTab = "agents",
  onToggleCollapse,
  onSelectAgent,
  onPageChange,
  onNewSession,
  onSelectSession,
  onDeleteSession,
  onTabChange,
}: Props) {
  const [tab, setTab] = useState<LeftSidebarTab>(defaultTab);

  useEffect(() => {
    setTab(defaultTab);
  }, [defaultTab]);

  const switchTab = (next: LeftSidebarTab) => {
    setTab(next);
    onTabChange?.(next);
  };

  return (
    <aside
      className="relative flex h-full shrink-0 flex-col overflow-hidden border-r border-line bg-surface transition-[width] duration-200 ease-out"
      style={{ width: collapsed ? CHAT_LEFT_SIDEBAR_COLLAPSED : CHAT_LEFT_SIDEBAR_EXPANDED }}
    >
      <SidebarCollapseButton side="left" collapsed={collapsed} onToggle={onToggleCollapse} />

      {collapsed ? (
        <>
          <div className="flex flex-col items-center gap-1 border-b border-line-soft py-2">
            <button
              type="button"
              title="智能体"
              onClick={() => switchTab("agents")}
              className={`flex h-8 w-8 items-center justify-center rounded-lg text-xs transition ${
                tab === "agents" ? "bg-brand-light text-brand" : "text-ink-faint hover:text-ink"
              }`}
            >
              AI
            </button>
            <button
              type="button"
              title="会话"
              onClick={() => switchTab("sessions")}
              className={`flex h-8 w-8 items-center justify-center rounded-lg transition ${
                tab === "sessions" ? "bg-brand-light text-brand" : "text-ink-faint hover:text-ink"
              }`}
            >
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M8 10h8M8 14h5M6 6h12a2 2 0 012 2v8l-3 3H6a2 2 0 01-2-2V8a2 2 0 012-2z"
                />
              </svg>
            </button>
          </div>
          {tab === "agents" ? (
            <ul className="flex flex-1 flex-col items-center gap-1 overflow-y-auto py-2">
              {agents.map((a) => (
                <li key={a.id}>
                  <button
                    type="button"
                    title={`${a.name} · ${agentModeLabel(a)}`}
                    onClick={() => onSelectAgent(a.id)}
                    className={`flex h-9 w-9 items-center justify-center rounded-lg text-sm font-medium transition ${
                      selectedAgentId === a.id
                        ? "bg-brand text-brand-foreground shadow-sm"
                        : "text-ink-muted hover:bg-brand-light hover:text-brand"
                    }`}
                  >
                    {agentInitial(a.name)}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <div className="flex flex-1 flex-col items-center gap-2 py-2">
              <button
                type="button"
                title="新会话"
                disabled={!selectedAgentId}
                onClick={onNewSession}
                className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand text-lg text-brand-foreground disabled:opacity-40"
              >
                +
              </button>
              <ul className="flex flex-1 flex-col items-center gap-1 overflow-y-auto">
                {sessions.slice(0, 12).map((s) => (
                  <li key={s.id}>
                    <button
                      type="button"
                      title={s.title}
                      onClick={() => onSelectSession(s.id)}
                      className={`h-2 w-2 rounded-full transition ${
                        s.id === activeSessionId ? "bg-brand" : "bg-line hover:bg-brand/50"
                      }`}
                    />
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      ) : (
        <>
          <div className="flex shrink-0 border-b border-line-soft p-1.5">
            {(
              [
                { id: "agents" as const, label: "智能体" },
                { id: "sessions" as const, label: "会话" },
              ] as const
            ).map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => switchTab(item.id)}
                className={`flex-1 rounded-md py-2 text-center text-xs font-medium transition ${
                  tab === item.id
                    ? "bg-surface text-brand shadow-sm"
                    : "text-ink-muted hover:text-ink"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>

          {tab === "agents" ? (
            <>
              <div className="border-b border-line-soft px-4 py-2.5">
                <p className="text-xs text-ink-faint">共 {total} 个智能体</p>
              </div>
              <ul className="min-h-0 flex-1 overflow-y-auto p-2">
                {agents.map((a) => (
                  <li key={a.id}>
                    <button
                      type="button"
                      onClick={() => onSelectAgent(a.id)}
                      className={`mb-1 w-full rounded-lg border px-3 py-2.5 text-left text-sm transition ${
                        selectedAgentId === a.id
                          ? "border-brand/30 bg-brand-light"
                          : "border-transparent hover:border-line hover:bg-brand-light/40"
                      }`}
                    >
                      <p className="font-medium text-ink">{a.name}</p>
                      <p className="mt-0.5 text-xs text-ink-muted">{agentModeLabel(a)}</p>
                    </button>
                  </li>
                ))}
              </ul>
              <div className="shrink-0 border-t border-line-soft p-2">
                <ResourceListFooter
                  page={page}
                  size={size}
                  total={total}
                  onPageChange={onPageChange}
                />
              </div>
            </>
          ) : (
            <AgentChatSessionPanel
              agentSelected={Boolean(selectedAgentId)}
              sessions={sessions}
              activeSessionId={activeSessionId}
              onNewSession={onNewSession}
              onSelectSession={onSelectSession}
              onDeleteSession={onDeleteSession}
            />
          )}
        </>
      )}
    </aside>
  );
}
