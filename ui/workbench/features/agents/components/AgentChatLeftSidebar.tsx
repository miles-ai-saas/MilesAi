"use client";

/** 对话页左侧：智能体列表与会话切换（链路 §5）。 */

import { AgentChatAgentColumn } from "@/features/agents/components/AgentChatAgentColumn";
import { AgentChatSessionColumnCompact } from "@/features/agents/components/AgentChatSessionColumnCompact";
import { AgentChatSessionPanel } from "@/features/agents/components/AgentChatSessionPanel";
import {
  CHAT_AGENT_COLUMN,
  CHAT_AGENT_COLUMN_COMPACT,
  CHAT_LEFT_SIDEBAR_COLLAPSED,
  CHAT_LEFT_SIDEBAR_EXPANDED,
  CHAT_SESSION_COLUMN,
} from "@/features/agents/hooks/use-agents-chat-layout";
import type { ChatSession } from "@/features/agents/lib/chat-sessions";
import type { Agent } from "@/lib/types";

type Props = {
  agents: Agent[];
  total: number;
  selectedAgentId: string;
  sessions: ChatSession[];
  activeSessionId: string | null;
  collapsed: boolean;
  agentsColumnCompact?: boolean;
  hideCollapseButton?: boolean;
  hasMoreAgents: boolean;
  loadingMoreAgents: boolean;
  onLoadMoreAgents: () => void;
  onToggleCollapse: () => void;
  onSelectAgent: (id: string) => void;
  onNewSession: () => void;
  onSelectSession: (id: string) => void;
  onRenameSession: (sessionId: string, title: string) => void;
  onDeleteSession: (id: string) => void;
};

export function AgentChatLeftSidebar({
  agents,
  total,
  selectedAgentId,
  sessions,
  activeSessionId,
  collapsed,
  agentsColumnCompact = false,
  hideCollapseButton,
  hasMoreAgents,
  loadingMoreAgents,
  onLoadMoreAgents,
  onToggleCollapse,
  onSelectAgent,
  onNewSession,
  onSelectSession,
  onRenameSession,
  onDeleteSession,
}: Props) {
  const agentColumnProps = {
    agents,
    total,
    selectedAgentId,
    hasMore: hasMoreAgents,
    loadingMore: loadingMoreAgents,
    onLoadMore: onLoadMoreAgents,
    onSelectAgent,
  };

  const width = collapsed ? CHAT_LEFT_SIDEBAR_COLLAPSED : CHAT_LEFT_SIDEBAR_EXPANDED;

  return (
    <div className="relative h-full shrink-0 transition-[width] duration-200 ease-out" style={{ width }}>
      <aside className="flex h-full w-full flex-col overflow-hidden border-r border-line bg-surface">
      {collapsed ? (
        <div className="flex min-h-0 flex-1 flex-col">
          <AgentChatAgentColumn {...agentColumnProps} compact />
          <AgentChatSessionColumnCompact
            selectedAgentId={selectedAgentId}
            sessions={sessions}
            activeSessionId={activeSessionId}
            onNewSession={onNewSession}
            onSelectSession={onSelectSession}
          />
        </div>
      ) : (
        <div className="flex min-h-0 flex-1">
          <div
            className="flex min-h-0 shrink-0 flex-col border-r border-line-soft"
            style={{
              width: agentsColumnCompact && selectedAgentId ? CHAT_AGENT_COLUMN_COMPACT : CHAT_AGENT_COLUMN,
            }}
          >
            <AgentChatAgentColumn {...agentColumnProps} compact={Boolean(agentsColumnCompact && selectedAgentId)} />
          </div>
          <div
            className="flex min-h-0 min-w-0 flex-1 flex-col"
            style={agentsColumnCompact && selectedAgentId ? undefined : { width: CHAT_SESSION_COLUMN, flex: "none" }}
          >
            <div className="shrink-0 border-b border-line-soft px-3 py-2.5">
              <p className="text-xs font-medium text-ink">会话</p>
              <p className="mt-0.5 truncate text-[10px] text-ink-faint">{selectedAgentId ? "当前智能体的对话记录" : "选择智能体后显示"}</p>
            </div>
            <AgentChatSessionPanel
              agentSelected={Boolean(selectedAgentId)}
              sessions={sessions}
              activeSessionId={activeSessionId}
              onNewSession={onNewSession}
              onSelectSession={onSelectSession}
              onRenameSession={onRenameSession}
              onDeleteSession={onDeleteSession}
            />
          </div>
        </div>
      )}
      </aside>
      <SidebarCollapseButton side="left" collapsed={collapsed} onToggle={onToggleCollapse} hidden={hideCollapseButton} />
    </div>
  );
}

function SidebarCollapseButton({
  side,
  collapsed,
  onToggle,
  hidden,
}: {
  side: "left" | "right";
  collapsed: boolean;
  onToggle: () => void;
  hidden?: boolean;
}) {
  if (hidden) return null;
  const label = collapsed ? "展开侧栏" : "收起侧栏";
  const chevron = side === "left" ? (collapsed ? "M9 6l6 6-6 6" : "M15 6l-6 6 6 6") : collapsed ? "M15 6l-6 6 6 6" : "M9 6l6 6-6 6";

  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={label}
      title={label}
      className={`absolute top-1/2 z-40 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-full border border-line bg-surface text-ink-muted shadow-sm transition hover:border-brand/30 hover:text-brand ${
        side === "left" ? "-right-3.5" : "-left-3.5"
      }`}
    >
      <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path strokeLinecap="round" strokeLinejoin="round" d={chevron} />
      </svg>
    </button>
  );
}
